from collections import OrderedDict
import sys
import os
import json
import dataset
from datetime import datetime, date
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from db import db


slack_client = WebClient(token=os.environ["SLACK_BOT_TOKEN"])
slack_channel = os.environ["SLACK_CHANNEL_ID"]


def fetch_entries() -> list[dict]:
    with db as tx:
        tx: dataset.Database
        certificates: dataset.Table = tx["Certificates"]
        order = certificates.find(order_by=['Valid_To'])
    return [item for item in order]

def organize_entries(entries: list[dict], base: date = date.today()):
    thresholds = [0, 14, 30, 90]
    groups = [[],]
    empties = []


def calc_remain(item: dict, base: date = None) -> int | None:
    valid_to: date = item['Valid_To']
    if valid_to is None:
        return None
    if base is None:
        base = datetime.now().date()
    return (valid_to - base).days





def make_message9(list9, base: date = None):
    header = "FROM-date, EXPIRY-date, `[残日数 ]`, `調査対象ドメイン   `, common-name        , signature-algorithm    , issuer      , スキャン日時\n"
    format_str = "• {}, {}, `[{:3}days]`, `{:19}`, {:19}, {}, {}, {}\n"

    msg_u30=""
    filter_u30 = list(filter(lambda x: 14 <= x[8] <= 30, list9))
    if filter_u30:
        msg_u30 = "=========証明書失効まで30日切った人たちでーす========\n"
        msg_u30 += header
        for tpl in filter_u30:
            msg_u30 += format_str.format(tpl[5], tpl[6], tpl[8], tpl[1], tpl[2], tpl[4], tpl[3], tpl[7])
        msg_u30 += ""

    msg_u90=""
    filter_u90 = list(filter(lambda x: 31 <= x[8] <= 90, list9))
    if filter_u90:
        msg_u90 = "=========証明書失効まで90日切った人たちでーす========\n"
        msg_u90 += header
        for tpl in filter_u90:
            msg_u90 += format_str.format(tpl[5], tpl[6], tpl[8], tpl[1], tpl[2], tpl[4], tpl[3], tpl[7])
        msg_u90 += ""

    msg_o90=""
    filter_o90 = list(filter(lambda x: 91 <= x[8], list9))
    if filter_o90:
        msg_o90 = "=========残り91日以上あります========\n"
        msg_o90 += header
        for tpl in filter_o90:
            msg_o90 += format_str.format(tpl[5], tpl[6], tpl[8], tpl[1], tpl[2], tpl[4], tpl[3], tpl[7])
        msg_o90 += ""

    return(msg_u30,msg_u90,msg_o90)

def make_message8(list8):
    
    msg=""
    if list8:
        msg = "=========分析不可(証明書が取得できない等)========\n"
        for tpl in list8:
            msg += "{}\n".format(tpl[1])
    msg += ""

    return msg

def post_message():
    try:
        entries = fetch_entries()
        
        list_asc,list_null = calc_remain()
        u30,u90,o90 = make_message9(list_asc)
        na = make_message8(list_null)
        
        print(u30)
        print(u90)
        print(o90)
        print(na)

        if u30:
            blocks_list = [{"type": "section", "text": {"type": "mrkdwn", "text": u30}}]
            response = slack_client.chat_postMessage(channel=slack_channel,blocks=blocks_list,as_user=True)
            print("slackResponse: ", response)
        if u90:
            blocks_list = [{"type": "section", "text": {"type": "mrkdwn", "text": u90}}]
            response = slack_client.chat_postMessage(channel=slack_channel,blocks=blocks_list,as_user=True)
            print("slackResponse: ", response)
        if o90:
            blocks_list = [{"type": "section", "text": {"type": "mrkdwn", "text": o90}}]
            response = slack_client.chat_postMessage(channel=slack_channel,blocks=blocks_list,as_user=True)
            print("slackResponse: ", response)
        if na:
            blocks_list = [{"type": "section", "text": {"type": "mrkdwn", "text": na}}]
            response = slack_client.chat_postMessage(channel=slack_channel,blocks=blocks_list,as_user=True)
            print("slackResponse: ", response)
        
    except SlackApiError as e:
        print("Error posting message: {}".format(e))
  
    
if __name__=="__main__":
    
    post_message()
