from datetime import datetime, timedelta
from typing import Self

import monzo_pots
from monzo.authentication import Authentication
from monzo.endpoints.account import Account


class PotManager(object):
    def __init__(self, auth: Authentication, account: Account, pots: list[monzo_pots.MonzoPot]):
        self.auth = auth
        self.account = account
        self.pots = pots

    @classmethod
    def from_account(cls, auth: Authentication, account: Account) -> Self:
        pots = monzo_pots.fetch_pots(auth, account, datetime.now() - timedelta(days=1))
        return cls(auth, account, pots)

    def update_pots(self):
        self.pots = monzo_pots.fetch_pots(self.auth, self.account, datetime.now() - timedelta(days=1))
