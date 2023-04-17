import logging
import os
import re
from typing import Callable, Optional
import dotenv
from slack_sdk import WebClient
from slack_bolt import App, BoltResponse
from slack_bolt.adapter.socket_mode import SocketModeHandler
from click.testing import CliRunner, Result
from command import cli  # noqa E402


dotenv.load_dotenv()
# Slack APIトークンを取得
SLACK_APP_TOKEN = os.environ["SLACK_APP_TOKEN"]
SLACK_BOT_TOKEN = os.environ["SLACK_BOT_TOKEN"]

app = App(token=SLACK_BOT_TOKEN)
client = WebClient(token=SLACK_BOT_TOKEN)

env = {
    'DATABASE': os.environ['DATABASE'],
}
help_text = """\
/scanner list          ... List all registered domains
/scanner show DOMAIN   ... Show a registered domain info
/scanner add DOMAIN    ... Register a domain
/scanner delete DOMAIN ... Unregister a domain
/scanner scan DOMAIN   ... Scan a registered domain\
"""


# Slashコマンドに対応するアクションを定義する
@app.event('message')
def scanner_bot_messaged(ack: Callable[[Optional[str]], BoltResponse], body: dict):
    print(body)
    ack()
    pass


@app.event('app_mention')
def scanner_bot_mentioned(ack: Callable[[Optional[str]], BoltResponse], body: dict):
    args = unurl(body["event"]["text"]).split()
    # 先頭にはメンション文字列が入っているため、2つ目以降を利用
    args.pop(0)
    user_id = body["event"]["user"]
    channel_id = body["event"]["channel"]
    print(args, user_id, channel_id)
    scanner_bot(ack, args, user_id, channel_id)


@app.command("/scanner")
def scanner_bot_slash_command(ack: Callable[[Optional[str]], BoltResponse], body: dict):
    args = unurl(body["text"]).split()
    user_id = body["user_id"]
    channel_id = body["channel_id"]
    logging.info(f"[Event][Slash] {body['text']} from {body['user_name']}")
    # slashコマンドでは、コマンド自体は別変数に、textにはコマンドの続きの文字列が入っているため、1つ目から利用
    print(args, user_id, channel_id)
    scanner_bot(ack, args, user_id, channel_id)


def scanner_bot(ack: Callable[[Optional[str]], BoltResponse], args: list, user_id: str, channel_id: str):
    if (len(args) == 0) or (args[0] == "help"):
        acked: BoltResponse = ack()
        slack_post_message(
            channel=channel_id,
            header="[Scanner] Hello ! May I help you ?",
            code=help_text,
            ephemeral_user_id=user_id)

    elif args[0] == "list":
        acked: BoltResponse = ack()
        (ok, msg, result) = run("list")
        slack_post_message(
            channel=channel_id,
            header="[Scanner] List registered domains",
            code=msg,
            ephemeral_user_id=user_id)

    elif args[0] == "show" and len(args) == 2:
        acked: BoltResponse = ack()
        print(acked.status, acked.body, acked.headers)
        (ok, msg, result) = run("show", args[1])
        slack_post_message(
            channel=channel_id,
            header="[Scanner] Show registered domains",
            code=msg,
            ephemeral_user_id=user_id)

    elif args[0] == "add" and len(args) == 2:
        acked: BoltResponse = ack()
        print(acked.status, acked.body, acked.headers)
        (ok, msg, result) = run("add", args[1])
        slack_post_message(
            channel=channel_id,
            header="[Scanner] Add registered domains",
            code=msg,
            ephemeral_user_id=user_id)

    elif args[0] == "delete" and len(args) == 2:
        acked: BoltResponse = ack()
        print(acked.status, acked.body, acked.headers)
        (ok, msg, result) = run("delete", args[1])
        slack_post_message(
            channel=channel_id,
            header="[Scanner] Delete registered domains",
            code=msg,
            ephemeral_user_id=user_id)

    elif args[0] == "scan" and len(args) == 2:
        acked: BoltResponse = ack()
        print(acked.status, acked.body, acked.headers)
        (ok, msg, result) = run("show", args[1])
        if ok:
            ack()
            (ok, msg, result) = run("scan", args[1])
            if ok:
                slack_post_message(
                    channel=channel_id,
                    header=f"<@{user_id}> Scan '{args[1]}' completed !",
                    code=msg,
                    ephemeral_user_id=user_id)
            else:
                slack_post_message(
                    channel=channel_id,
                    header=f"<@{user_id}> Scan '{args[1]}' failed...",
                    code=msg,
                    ephemeral_user_id=user_id)
        else:
            ack("{args[1]} is not registered yet. Please register with '/scanner add DOMAIN'")

    else:
        ack()
        slack_post_message(
            channel=channel_id,
            header="[Scanner] Sorry... I can't understand your order. Can I help you ?",
            code=help_text,
            ephemeral_user_id=user_id)


def run(cmd, *args) -> Result:
    result = CliRunner().invoke(cli=cli, env=env, args=[cmd, *args])
    ok = result.exit_code == 0
    msg = result.stdout if ok else result.stderr
    return (ok, msg.strip(), result)


# Sub-functions

def slack_post_message(channel: str, header: str, code: str = None, thread_ts: str = None, ephemeral_user_id: str = None):
    """ Slackにメッセージを投稿します。
    見出しと、それに続く長いコードブロックを投稿することを想定したフォーマットを使用します。

    Args:
        channel (str): Slack channel ID
        header (str): 見出しになるメッセージ。ここはコードブロックの外に通常のテキストとして投稿されます。
        code (str): コードブロックとして投稿されます。長過ぎる場合は適切に分割して複数メッセージとして投稿されます。
    """
    chunk_size = 3000
    for post_block in iterate_slack_code_post_chunks(header, code, chunk_size=chunk_size):
        try:
            args = dict(channel=channel, as_user=True, thread_ts=thread_ts)
            if ephemeral_user_id:
                response = client.chat_postEphemeral(**args, text=post_block["text"]["text"], user=ephemeral_user_id)
            else:
                response = client.chat_postMessage(**args, blocks=[post_block])
            print("slackResponse: ", response)
        except Exception as e:
            print("Error posting message: {}".format(e))


def iterate_message_chunks(msg: str, chunk_size=3000, first_chunk_size=None):
    """ 長いメッセージに対して、文字数が一定値以上にならないように複数ブロックに分割し、順に取り出すイテレータを生成します。

    * 行単位で評価され、「次の行を含めるとブロックサイズが制限値を超える」ところで分割されます
    * 一行の長さがブロックサイズを超える場合、その行の手前で一度ブロックを分割した上で、行の途中で分割して返します
    * 分割された各ブロックの最後には改行が含まれません(その位置にあった改行コードが削除されます)
    * 見出しなどを投稿することを考慮し、先頭ブロックの chunk_size だけ個別に指定することができます。

    Args:
        msg (str): 入力文字列
        chunk_size (int, optional): 分割する際の各ブロックの上限サイズです. Defaults to 3000.
        first_chunk_size (int, optional): 一番最初のブロックの上限サイズです。None指定でchunk_sizeと同じ値になります。 Defaults to None.

    Yields:
        str: 分割された文字列の塊です。
    """
    if first_chunk_size is None:
        first_chunk_size = chunk_size
    fold_marker = ""
    fold_marker_size = len(fold_marker)
    chunk_buffer = []
    current_chunk_size = first_chunk_size
    rest_chunk_size = first_chunk_size

    for line in msg.split("\n"):
        line_size = len(line) + len("\n")
        # 一行のサイズがそもそもchunk sizeを超えていたら一行を分割する。
        # ただし、行の開始を必ずchunkの開始に合わせる。
        #
        # 1. 一度そこでchunkを返して次のブロックへ
        # 2. 一行をchunk_sizeで分割して入るだけ詰めて応答 → 繰り返し
        # 3. このまま行末すすめて、最後のブロックだけは通常の1行の処理へ進む
        if line_size >= current_chunk_size:
            # 長い行がなるべくブロックの途中から中途半端に始まらないよう、
            if len(chunk_buffer) > 0:
                yield "\n".join(chunk_buffer)
                chunk_buffer.clear()
                current_chunk_size = chunk_size
                rest_chunk_size = chunk_size
            # 折返しマーカを含めてchunkの中に収まるように行を分割する
            fold_limit = current_chunk_size - (fold_marker_size + len("\n"))
            folded_line = [line[x:x + fold_limit] for x in range(0, len(line), fold_limit)]
            # 最後のブロックだけは折返しマーカを入れなくて良いので、サイズを見て収まりそうならまとめる
            if len(folded_line[-1]) <= (fold_marker_size + len("\n")):
                folded_line[-2] += folded_line[-1]
                folded_line.pop()
            # 折返した行の先頭を返す。マーカーなし。必ずchunkサイズギリギリになる
            yield folded_line.pop(0)
            # 折り返し後最終行を除いて返す。マーカーあり。改行は含みません。
            while len(folded_line) > 1:
                yield fold_marker + folded_line.pop(0)
            # 最終行がのこったらlineに渡して通常処理に回す。マーカーあり。
            line = fold_marker + folded_line.pop(0)
            line_size = len(line)
            rest_chunk_size = chunk_size - line_size

        # 改行込みで残容量を超えていたら、一度メッセージブロックを返す
        if line_size >= rest_chunk_size:
            yield "\n".join(chunk_buffer)
            # 次のブロックを作成するための準備
            chunk_buffer.clear()
            current_chunk_size = chunk_size
            rest_chunk_size = chunk_size
            # このまま、処理中の行をブロック生成処理に回す
        # 行をブロックに追加
        chunk_buffer.append(line)
        rest_chunk_size -= line_size
    # バッファに残った行があれば最後に返す
    yield "\n".join(chunk_buffer)


def iterate_slack_code_post_chunks(header: str, code: str = None, chunk_size: int = 3000):
    """ Slackに「見出しと、長いコードブロック」を投稿する際の、メッセージを生成します。

    見出しの文字をそのままの文字で、コード部分は "```" で囲まれて返されます。
    コード部分は投稿サイズの上限を意識して改行位置を基準に分割して返されます。

    Args:
        header (str): _description_
        code (str): _description_
        chunk_size (int, optional): _description_. Defaults to 3000.

    Yields:
        _type_: _description_
    """
    if code is None:
        yield {"type": "section", "text": {"type": "mrkdwn", "text": header}}
        return

    header += "\n"
    code_start = "```\n"
    code_end = "\n```"
    # 改行と囲み文字(```)を考慮して最大のブロックサイズを計算します。先頭ブロックは見出し投稿のサイズを差し引きます。
    real_first_chunk_size = chunk_size - (len(header) + len(code_start) + len(code_end))
    real_chunk_size = chunk_size - (len(code_start) + len(code_end))
    message_blocks = [m for m in
                      iterate_message_chunks(code,
                                             chunk_size=real_chunk_size,
                                             first_chunk_size=real_first_chunk_size)]
    # The first message
    msg = message_blocks.pop(0)
    body = f"{header}{code_start}{msg}{code_end}"
    yield {"type": "section", "text": {"type": "mrkdwn", "text": body}}

    # Following messages
    for msg in message_blocks:
        body = f"{code_start}{msg}{code_end}"
        yield {"type": "section", "text": {"type": "mrkdwn", "text": body}}


def unurl(text):
    # `<http://example.com|example.com>` のようなリンクを 'example.com' に戻す
    return re.sub(r'<(http[s]?://[^\|]+)\|([^>]+)>', r'\2', text)


if __name__ == "__main__":
    result: Result = CliRunner().invoke(cli=cli, env=env, args=['init'])
    if result.exit_code != 0:
        print("Error: DB failed.")
        print(result.stdout)
    else:
        try:
            handler = SocketModeHandler(app_token=SLACK_APP_TOKEN, app=app)
            handler.start()
        except KeyboardInterrupt:
            handler.close()
