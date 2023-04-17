import dataset


class SSLScannerDatabase():

    def __init__(self, dbstring: str, table_name: str = "Certificates") -> None:
        self._db = dataset.connect(dbstring)
        self._table_name = table_name

    @property
    def db(self):
        return self._db

    @property
    def table(self):
        if self.has_table:
            return self._db.get_table(self.table_name)

    @property
    def table_name(self) -> str:
        return self._table_name

    @property
    def has_table(self) -> bool:
        return self.db.has_table(self.table_name)

    def drop_table(self):
        self.table.drop()

    def create_table(self) -> dataset.Table:
        self.db.create_table(self.table_name, primary_id="ID")
        return self.migrate_table()

    def migrate_table(self) -> dataset.Table:
        table = self.table
        columns = self.get_column_definitions()
        for column in columns:
            if not table.has_column(column[0]):
                table.create_column(column[0], **(column[1]))
        return table

    def get_column_definitions(self) -> list[tuple[str, dict]]:
        db = self.db
        return [
            ("Domain", dict(type=db.types.string(256), unique=True)),
            ("Subject", dict(type=db.types.text)),
            ("Issuer", dict(type=db.types.text)),
            ("SigAlgorithm", dict(type=db.types.text)),
            ("Valid_From", dict(type=db.types.date)),
            ("Valid_To", dict(type=db.types.date)),
            ("Last_Check", dict(type=db.types.datetime)),
            ("CertSerial", dict(type=db.types.text)),
            ("PeerAddress", dict(type=db.types.text)),
        ]

    def prepair_table(self, drop_exists=False) -> dataset.Table:
        """
        Prepare 'Certificates' table on the database.

        The target database is determined at the time this module is loaded into the application.

        Args:
            drop_exists (bool, optional):
                If True, the existing table will be dropped and recreated.
                Defaults to False.

        Returns:
            dataset.Table: An instance to communicate with the table.
        """
        if self.has_table and drop_exists:
            self.drop_table()
        if self.has_table:
            table = self.table
            if not table.has_column("ID"):
                raise Exception(f"Unexpected formatted table '{self.table_name}' in the database.")
            self.migrate_table()
        else:
            table = self.create_table()
        return table

    def populate_table(self, domains: list):
        """
        Add entries into "Certificates" table.

        Args:
            domains (list): A list of "domain" strings to be inserted.
        """
        self.table.insert_many([dict(Domain=d) for d in domains])
