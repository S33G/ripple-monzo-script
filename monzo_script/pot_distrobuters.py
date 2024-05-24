from collections import defaultdict
from dataclasses import dataclass

from monzo_pots import MonzoPot
from transaction_controlers import AccountTransactionGroupInterface


@dataclass
class PotTarget:
    pot: MonzoPot
    target: int
    priority: int


def priority_distribution(
    src_pot: MonzoPot,
    dest_pots: list[PotTarget],
    tc: AccountTransactionGroupInterface,
    src_percentage: float = 1,
    funding_amount_max: int = 0,
):
    if tc.get_pot_factored_balance(src_pot) > 0:
        priority_dest_pots: defaultdict[int, list[PotTarget]] = defaultdict(list)
        for dest_pot in dest_pots:
            priority_dest_pots[dest_pot.priority].append(dest_pot)
        weighted_dest_pots = sorted(priority_dest_pots.values(), key=lambda x: x[0].priority, reverse=True)
        funding_balance_acc = int(tc.get_pot_factored_balance(src_pot) * src_percentage)
        if funding_amount_max != 0 and funding_balance_acc > funding_amount_max:
            funding_balance = funding_amount_max
        else:
            funding_balance = funding_balance_acc
        for pot_targets in weighted_dest_pots:
            num_pots = len(pot_targets)
            sorted_pot_targets = sorted(pot_targets, key=lambda x: tc.get_pot_balance(x.pot) - x.target, reverse=True)
            for pot_target in sorted_pot_targets:
                if funding_balance > 0:
                    pot_amount = int(funding_balance / num_pots)
                    # if the pot is below minimum this will be negative with the amount needed to reach minimum
                    pot_balance = tc.get_pot_balance(pot_target.pot)
                    pot_needed = pot_target.target - pot_balance if pot_balance < pot_target.target else 0
                    transaction_amount = pot_needed if pot_needed < pot_amount else pot_amount
                    if transaction_amount > 0:
                        tc.transfer_between_pots(src_pot, pot_target.pot, transaction_amount)
                        funding_balance -= transaction_amount
                    num_pots -= 1
                else:
                    break
            else:
                continue
            break


def weighted_distribution(
    src_pot: MonzoPot, dest_pots: list[PotTarget], tc: AccountTransactionGroupInterface, src_percentage: float = 1
):
    if tc.get_pot_factored_balance(src_pot) > 0:
        priority_slices = sum(pot.priority for pot in dest_pots)
        sorted_pot_targets = sorted(
            dest_pots, key=lambda x: (tc.get_pot_balance(x.pot) - x.target) / (x.priority or 1), reverse=True
        )
        funding_balance = int(tc.get_pot_factored_balance(src_pot) * src_percentage)
        for pot_target in sorted_pot_targets:
            if pot_target.priority:
                if funding_balance > 0:
                    priorty_slice = int(funding_balance / priority_slices)
                    pot_amount_weighted = priorty_slice * pot_target.priority
                    pot_balance = tc.get_pot_balance(pot_target.pot)
                    pot_needed = pot_target.target - pot_balance if pot_balance < pot_target.target else 0
                    transaction_amount = pot_needed if pot_needed < pot_amount_weighted else pot_amount_weighted
                    if transaction_amount > 0:
                        tc.transfer_between_pots(src_pot, pot_target.pot, transaction_amount)
                    priority_slices -= pot_target.priority
                    funding_balance -= transaction_amount
                else:
                    break
