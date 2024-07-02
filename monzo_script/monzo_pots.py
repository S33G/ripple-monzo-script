import time
from datetime import datetime
from uuid import uuid4

from monzo.authentication import Authentication
from monzo.endpoints.account import Account
from monzo.endpoints.pot import Pot
from monzo.endpoints.transaction import Transaction
import logging

logger = logging.getLogger(__name__)

class MonzoPot(object):
    def __init__(
        self,
        auth: Authentication,
        pot: Pot,
        account: Account,
        credit_transactions: list[Transaction],
        debit_transactions: list[Transaction],
    ):
        self.pot = pot
        self.credit_transactions = credit_transactions
        self.debit_transactions = debit_transactions
        self.auth = auth
        self.account = account

    @classmethod
    def from_transaction_history(cls, pot: Pot, transactions: list[Transaction], auth: Authentication, account: Account):
        debit_transactions = list()
        credit_transactions = list()
        for transaction in transactions:
            if transaction.metadata.get("pot_id", "") == pot.pot_id:
                if transaction.amount < 0:
                    credit_transactions.append(transaction)
                elif transaction.amount > 0:
                    debit_transactions.append(transaction)
        return cls(auth, pot, account, credit_transactions, debit_transactions)

    @property
    def is_savings(self) -> bool:
        return not self.pot.pot_type == "default"

    @property
    def metadata(self) -> dict[str, str]:
        pot_metadata: dict[str, str] = {
            "name": "",
            "weighted_priority": "1",
            "minimum_priority": "1",
            "minimum_amount": "0",
            "minimum_transfer_date": "0",
            "roundup_minimum": "0",
            "roundup_value": "0",
            "funding_priority": "0",
            "saving_value": "0",
            "saving_priority": "0",
        }
        pot_data = self.pot.name.strip().split(" ")
        if ":" in pot_data[-1]:
            *name, metadata = pot_data
            for metadatum in metadata.split(","):
                try:
                    flag, data = metadatum.split(":")
                    if flag == "WP":
                        pot_metadata["weighted_priority"] = data
                    elif flag == "MP":
                        pot_metadata["minimum_priority"] = data
                    elif flag == "MTD":
                        pot_metadata["minimum_transfer_date"] = data
                    elif flag == "RV":
                        pot_metadata["roundup_value"] = data
                    elif flag == "RM":
                        pot_metadata["roundup_minimum"] = data
                    elif flag == "M":
                        pot_metadata["minimum_amount"] = data
                    elif flag == "FP":
                        pot_metadata["funding_priority"] = data
                    elif flag == "SV":
                        pot_metadata["saving_value"] = data
                    elif flag == "SP":
                        pot_metadata["saving_priority"] = data
                except ValueError:
                    pass
            pot_metadata["name"] = " ".join(name)
        else:
            pot_metadata["name"] = self.pot.name

        return pot_metadata

    @property
    def name(self) -> str:
        return self.metadata["name"]

    @property
    def weighted_priority(self) -> int:
        return int(self.metadata["weighted_priority"])

    @property
    def minimum_priority(self) -> int:
        return int(self.metadata["minimum_priority"])

    @property
    def minimum_transfer_date(self) -> int:
        return int(self.metadata["minimum_transfer_date"])

    @property
    def minimum_amount(self) -> int:
        return int(self.metadata["minimum_amount"]) * 100

    @property
    def roundup_minimum(self) -> int:
        return int(self.metadata["roundup_minimum"]) * 100

    @property
    def roundup_account(self) -> bool:
        return self.roundup_minimum or self.roundup_value

    @property
    def funding_source(self) -> bool:
        return self.funding_priority != 0

    @property
    def funding_priority(self) -> int:
        return int(self.metadata["funding_priority"])

    @property
    def roundup_value(self) -> float:
        return int(self.metadata["roundup_value"]) * 0.01

    @property
    def saving_value(self) -> float:
        return int(self.metadata["saving_value"]) * 0.01

    @property
    def saving_priority(self) -> int:
        return int(self.metadata["saving_priority"])

    @property
    def factored_balance(self) -> int:
        return self.pot.balance - self.minimum_amount

    @property
    def goal(self) -> int:
        return self.pot.goal_amount or 0

    @property
    def locked(self) -> bool:
        return self.pot.locked

    @property
    def balance(self) -> int:
        return self.pot.balance

    @property
    def pot_id(self) -> str:
        return self.pot.pot_id

    @property
    def locked_until(self) -> datetime | None:
        return self.pot.locked_until

    def send_to_pot(self, amount: int, pot: "MonzoPot") -> None:
        if self.pot.balance >= amount:
            self.withdraw(amount, self.account)
            pot.deposit(amount, self.account)

    def deposit(self, amount: int, account: Account) -> None:
        if amount > 0:
            Pot.deposit(self.auth, self.pot, account.account_id, amount, uuid4().hex)
            time.sleep(2)

    def withdraw(self, amount: int, account: Account) -> None:
        if amount > 0:
            Pot.withdraw(self.auth, self.pot, account.account_id, amount, uuid4().hex)
            time.sleep(2)


def fetch_pots(auth: Authentication, account: Account, transaction_since: datetime):
    account_id = account.account_id
    pots = Pot.fetch(auth, account.account_id)
    while True:
        try:
            transactions = Transaction.fetch(auth, account_id, since=transaction_since)
        except Exception as e:
            logger.exception(e)
            time.sleep(5)
            continue
        break
    monzo_pots: list[MonzoPot] = []
    for pot in pots:
        if not pot.deleted:
            monzo_pots.append(MonzoPot.from_transaction_history(pot, transactions, auth, account))
    return monzo_pots
