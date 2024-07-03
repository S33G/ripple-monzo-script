from typing import Protocol

import monzo_pots
import pot_distrobuters
from monzo.authentication import Authentication
from monzo.endpoints.account import Account
from pot_manager import PotManager
from transaction_controlers import AccountTransactionGroup, AccountTransactionGroupInterface
import datetime
import calendar
import logging

logger = logging.getLogger(__name__)


class AccountProcessorInterface(Protocol):
    def process(self, transaction_controller: AccountTransactionGroupInterface) -> None: ...


class PotMinimumProcessor(AccountProcessorInterface):
    def __init__(self, pot_manager: PotManager) -> None:
        self.pot_manager = pot_manager
        self.transfer_dates: dict[str, datetime.datetime] = {}

    def is_pot_ready(self, pot: monzo_pots.MonzoPot) -> bool:
        if pot.minimum_transfer_date:
            current_time = datetime.datetime.now()
            _, days_in_month = calendar.monthrange(current_time.year, current_time.month)
            transfer_date = min(pot.minimum_transfer_date, days_in_month)
            next_transfer = datetime.datetime(current_time.year, current_time.month, transfer_date)
            if current_time <= next_transfer:
                return False
            elif (
                self.transfer_dates.get(pot.pot_id) is not None
                and self.transfer_dates[pot.pot_id].month == next_transfer.month
            ):
                return False
        return True

    def post_pot_transfer(self, pot: monzo_pots.MonzoPot):
        if pot.minimum_transfer_date:
            current_time = datetime.datetime.now()
            _, days_in_month = calendar.monthrange(current_time.year, current_time.month)
            transfer_date = min(pot.minimum_transfer_date, days_in_month)
            next_transfer = datetime.datetime(current_time.year, current_time.month, transfer_date)
            self.transfer_dates[pot.pot_id] = next_transfer

    def _get_minimum_pots(self) -> list[monzo_pots.MonzoPot]:
        minimum_pots: list[monzo_pots.MonzoPot] = []
        for pot in self.pot_manager.pots:
            if pot.minimum_amount and not pot.saving_priority and self.is_pot_ready(pot):
                minimum_pots.append(pot)
        return minimum_pots

    def _get_funding_pots(self) -> list[monzo_pots.MonzoPot]:
        funding_pots: list[monzo_pots.MonzoPot] = []
        for pot in self.pot_manager.pots:
            if pot.funding_source and not pot.locked and self.is_pot_ready(pot):
                funding_pots.append(pot)
        return funding_pots

    def process(self, transaction_controller: AccountTransactionGroupInterface) -> None:
        processing_pots = self._get_minimum_pots()
        funding_pots = sorted(self._get_funding_pots(), key=lambda pot: pot.funding_priority, reverse=True)
        processed_pots: list[monzo_pots.MonzoPot] = []
        for funding_pot in funding_pots:
            with transaction_controller.change_transaction_creator("PMP"):
                pots_transferred = pot_distrobuters.priority_distribution(
                    funding_pot,
                    [pot_distrobuters.PotTarget(pot, pot.minimum_amount, pot.minimum_priority) for pot in processing_pots],
                    transaction_controller,
                )
                if pots_transferred:
                    processed_pots.extend(map(lambda x: x[0], filter(lambda x: x not in processed_pots, pots_transferred)))
                    processed_pots.append(funding_pot)
        for pot in processed_pots:
            self.post_pot_transfer(pot)


class PotGoalProcessor(AccountProcessorInterface):
    def __init__(self, pot_manager: PotManager) -> None:
        self.pot_manager = pot_manager

    def _get_goal_pots(self) -> list[monzo_pots.MonzoPot]:
        dest_pots: list[monzo_pots.MonzoPot] = []
        for pot in self.pot_manager.pots:
            if pot.goal > 0 and not pot.is_savings and not pot.funding_source:
                dest_pots.append(pot)
        return dest_pots

    def _get_funding_pots(self) -> list[monzo_pots.MonzoPot]:
        funding_pots: list[monzo_pots.MonzoPot] = []
        for pot in self.pot_manager.pots:
            if pot.funding_source and not pot.locked and not pot.is_savings:
                funding_pots.append(pot)
        return funding_pots

    def process(self, transaction_controller: AccountTransactionGroupInterface) -> None:
        processing_pots = self._get_goal_pots()
        funding_pots = sorted(self._get_funding_pots(), key=lambda pot: pot.funding_priority, reverse=True)
        for funding_pot in funding_pots:
            with transaction_controller.change_transaction_creator("PGP"):
                pot_distrobuters.weighted_distribution(
                    funding_pot,
                    [
                        pot_distrobuters.PotTarget(
                            pot,
                            pot.goal,
                            pot.weighted_priority,
                        )
                        for pot in processing_pots
                    ],
                    transaction_controller,
                )


class SavingsPercentageProcessor(AccountProcessorInterface):
    def __init__(self, pot_manager: PotManager) -> None:
        self.pot_manager = pot_manager

    def _get_saving_pots(self) -> list[monzo_pots.MonzoPot]:
        dest_pots: list[monzo_pots.MonzoPot] = []
        for pot in self.pot_manager.pots:
            if pot.goal > 0 and pot.saving_priority:
                dest_pots.append(pot)
        return dest_pots

    def _get_funding_pots(self) -> list[monzo_pots.MonzoPot]:
        funding_pots: list[monzo_pots.MonzoPot] = []
        for pot in self.pot_manager.pots:
            if pot.funding_source and not pot.locked and not pot.saving_priority:
                funding_pots.append(pot)
        return funding_pots

    def process(self, transaction_controller: AccountTransactionGroupInterface) -> None:
        processing_pots = self._get_saving_pots()
        funding_pots = sorted(self._get_funding_pots(), key=lambda pot: pot.funding_priority, reverse=True)
        for funding_pot in funding_pots:
            with transaction_controller.change_transaction_creator("SPP"):
                pot_distrobuters.priority_distribution(
                    funding_pot,
                    [
                        pot_distrobuters.PotTarget(
                            pot,
                            pot.goal,
                            pot.saving_priority,
                        )
                        for pot in processing_pots
                    ],
                    transaction_controller,
                    float(funding_pot.saving_value),
                )


class SavingsOverflowProcessor(AccountProcessorInterface):
    def __init__(self, pot_manager: PotManager) -> None:
        self.pot_manager = pot_manager

    def _get_saving_pots(self) -> list[monzo_pots.MonzoPot]:
        dest_pots: list[monzo_pots.MonzoPot] = []
        for pot in self.pot_manager.pots:
            if pot.goal > 0 and pot.saving_priority:
                dest_pots.append(pot)
        return dest_pots

    def _get_funding_pots(self) -> list[monzo_pots.MonzoPot]:
        funding_pots: list[monzo_pots.MonzoPot] = []
        for pot in self.pot_manager.pots:
            if pot.funding_source and not pot.locked and not pot.saving_priority:
                funding_pots.append(pot)
        return funding_pots

    def process(self, transaction_controller: AccountTransactionGroupInterface) -> None:
        processing_pots = self._get_saving_pots()
        funding_pots = sorted(self._get_funding_pots(), key=lambda pot: pot.funding_priority, reverse=True)
        for funding_pot in funding_pots:
            with transaction_controller.change_transaction_creator("SOP"):
                pot_distrobuters.priority_distribution(
                    funding_pot,
                    [
                        pot_distrobuters.PotTarget(
                            pot,
                            pot.goal,
                            pot.saving_priority,
                        )
                        for pot in processing_pots
                    ],
                    transaction_controller,
                )


class RoundupProcessor(AccountProcessorInterface):
    def __init__(self, pot_manager: PotManager) -> None:
        self.pot_manager = pot_manager
        self.old_balances: dict[str, int] = {}

    def _get_saving_pots(self) -> list[monzo_pots.MonzoPot]:
        dest_pots: list[monzo_pots.MonzoPot] = []
        for pot in self.pot_manager.pots:
            if pot.goal > 0 and pot.saving_priority and not pot.roundup_account:
                dest_pots.append(pot)
        return dest_pots

    def _get_funding_pots(self) -> list[monzo_pots.MonzoPot]:
        funding_pots: list[monzo_pots.MonzoPot] = []
        for pot in self.pot_manager.pots:
            if pot.roundup_account and not pot.locked:
                funding_pots.append(pot)
        return funding_pots

    def process(self, transaction_controller: AccountTransactionGroupInterface) -> None:
        processing_pots = self._get_saving_pots()
        funding_pots = sorted(self._get_funding_pots(), key=lambda pot: pot.funding_priority, reverse=True)
        for funding_pot in funding_pots:
            with transaction_controller.change_transaction_creator("RP"):
                ballance_change = self.old_balances.get(funding_pot.pot_id, 0) - funding_pot.factored_balance
                if ballance_change > 0:
                    ra_amount = int(ballance_change * (funding_pot.roundup_value))
                    transaction_amount = ra_amount if ra_amount > funding_pot.roundup_minimum else funding_pot.roundup_minimum
                    pot_distrobuters.priority_distribution(
                        funding_pot,
                        [
                            pot_distrobuters.PotTarget(
                                pot,
                                pot.goal,
                                pot.saving_priority,
                            )
                            for pot in processing_pots
                        ],
                        transaction_controller,
                        funding_amount_max=transaction_amount,
                    )
                self.old_balances[funding_pot.pot_id] = transaction_controller.get_pot_factored_balance(funding_pot)


class AccountManager:
    def __init__(self, auth: Authentication, account: Account, pot_manager: PotManager, dry_run: bool = True) -> None:
        self.auth = auth
        self.account = account
        self.pot_manager = pot_manager
        self.dry_run = dry_run
        self.account_processors: list[AccountProcessorInterface] = []

    def _make_transaction_group(self) -> AccountTransactionGroupInterface:
        return AccountTransactionGroup.from_account(self.auth, self.account, self.pot_manager)

    def register_processor(self, processor: AccountProcessorInterface) -> None:
        self.account_processors.append(processor)

    def optimize_account(self) -> None:
        transaction_controler = self._make_transaction_group()
        for account_processor in self.account_processors:
            account_processor.process(transaction_controler)
        transaction_controler.execute(self.dry_run)
        self.pot_manager.update_pots()
