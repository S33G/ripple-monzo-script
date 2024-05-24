from typing import Self

import monzo_pots
from monzo.authentication import Authentication
from monzo.endpoints.account import Account
from pot_manager import PotManager
import logging

logger = logging.getLogger(__name__)

class AccountTransactionGroupInterface(object):
    @classmethod
    def from_account(cls, auth: Authentication, account: Account): ...

    def execute(self, dry_run: bool): ...

    def get_pot_balance(self, pot: monzo_pots.MonzoPot) -> int: ...

    def get_pot_factored_balance(self, pot: monzo_pots.MonzoPot) -> int: ...

    def transfer_between_pots(self, src_pot: monzo_pots.MonzoPot, dest_pot: monzo_pots.MonzoPot, amount: int): ...

    def transfer_account_to_pot(self, account: Account, dest_pot: monzo_pots.MonzoPot, amount: int): ...

    def transfer_pot_to_account(self, account: Account, src_pot: monzo_pots.MonzoPot, amount: int): ...

    def change_transaction_creator(self, transaction_creator: str) -> "AccountTransactionGroupInterface": ...

    def __enter__(self) -> "AccountTransactionGroupInterface": ...

    def __exit__(self, exc_type, exc_val, exc_tb) -> None: ...


class NoBalanceException(Exception):
    pass


class AccountTransactionGroup(AccountTransactionGroupInterface):
    def __init__(self, auth: Authentication, account: Account, account_balance: int, pots: list[monzo_pots.MonzoPot]) -> None:
        self.auth = auth
        self.account = account
        self.pots = pots
        self.account_balance = account_balance
        self.pot_balances: dict[str, int] = {}
        self.pot_factored_balances: dict[str, int] = {}
        self.pot_transactions: list[tuple[str, monzo_pots.MonzoPot, monzo_pots.MonzoPot, int]] = []
        self.pot_withdraw_transactions: list[tuple[str, Account, monzo_pots.MonzoPot, int]] = []
        self.pot_deposit_transactions: list[tuple[str, Account, monzo_pots.MonzoPot, int]] = []
        self.transaction_creator = "default"

    @classmethod
    def from_account(cls, auth: Authentication, account: Account, pot_manager: PotManager):
        pots = pot_manager.pots
        if account.balance:
            return cls(auth, account, account.balance.balance, pots)
        raise NoBalanceException("this account has no balance")

    def get_pot_balance(self, pot: monzo_pots.MonzoPot) -> int:
        return self.pot_balances.get(pot.pot_id, pot.balance)

    def get_pot_factored_balance(self, pot: monzo_pots.MonzoPot) -> int:
        return self.pot_factored_balances.get(pot.pot_id, pot.factored_balance)

    def _update_pot_balance(self, pot: monzo_pots.MonzoPot, amount: int):
        self.pot_balances[pot.pot_id] = self.pot_balances.get(pot.pot_id, pot.balance) + amount
        self.pot_factored_balances[pot.pot_id] = self.pot_factored_balances.get(pot.pot_id, pot.factored_balance) + amount

    def transfer_between_pots(self, src_pot: monzo_pots.MonzoPot, dest_pot: monzo_pots.MonzoPot, amount: int):
        if self.get_pot_balance(src_pot) >= amount:
            self.pot_transactions.append((self.transaction_creator, src_pot, dest_pot, amount))
            self._update_pot_balance(src_pot, -amount)
            self._update_pot_balance(dest_pot, amount)

    def transfer_account_to_pot(self, account: Account, dest_pot: monzo_pots.MonzoPot, amount: int):
        if self.account_balance >= amount:
            self.pot_deposit_transactions.append((self.transaction_creator, account, dest_pot, amount))
            self.account_balance -= amount
            self._update_pot_balance(dest_pot, amount)

    def transfer_pot_to_account(self, account: Account, src_pot: monzo_pots.MonzoPot, amount: int):
        if self.get_pot_balance(src_pot) >= amount:
            self.pot_withdraw_transactions.append((self.transaction_creator, account, src_pot, amount))
            self._update_pot_balance(src_pot, -amount)
            self.account_balance += amount

    def execute(self, dry_run: bool):
            for account_creator, src_pot, dest_pot, amount in self.pot_transactions:
                logger.info(
                    f"creator: ({account_creator}), sending funds from ({src_pot.name}) to ({dest_pot.name}), value moved: {amount}"
                )
                if not dry_run:
                    src_pot.send_to_pot(amount, dest_pot)

            for account_creator, account, src_pot, amount in self.pot_withdraw_transactions:
                logger.info(
                    f"creator: ({account_creator}), sending funds from ({src_pot.name}) to (main account), value moved: {amount}"
                )
                if not dry_run:
                    src_pot.withdraw(amount, account)

            for account_creator, account, dest_pot, amount in self.pot_deposit_transactions:
                logger.info(
                    f"creator: ({account_creator}), sending funds from ({src_pot.name}) to (main account), value moved: {amount}"
                )
                if not dry_run:
                    dest_pot.deposit(amount, account)

    def change_transaction_creator(self, transaction_creator: str) -> Self:
        self.transaction_creator = transaction_creator
        return self

    def __enter__(self) -> AccountTransactionGroupInterface:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.transaction_creator = "default"
