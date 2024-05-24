import logging
import sys
import time

from account_processor import (
    AccountManager,
    PotGoalProcessor,
    PotMinimumProcessor,
    RoundupProcessor,
    SavingsOverflowProcessor,
    SavingsPercentageProcessor,
)
from monzo.authentication import Authentication
from monzo.endpoints.account import Account
from monzo.handlers.filesystem import FileSystem
from pot_manager import PotManager

logger = logging.getLogger()
logger.setLevel(logging.INFO)

handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
handler.setFormatter(formatter)
logger.addHandler(handler)

handler = FileSystem(".creds")
creds = handler.fetch()
# Client ID obtained when creating Monzo client
CLIENT_ID = str(creds["client_id"])
# Client secret obtained when creating Monzo client
CLIENT_SECRET = str(creds["client_secret"])
REDIRECT_URI = "http://127.0.0.1/monzo"
ACCESS_TOKEN = str(creds["access_token"])
EXPIRY = int(creds["expiry"])
REFRESH_TOKEN = str(creds["refresh_token"])


auth = Authentication(
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET,
    redirect_url=REDIRECT_URI,
    access_token=ACCESS_TOKEN,
    access_token_expiry=EXPIRY,
    refresh_token=REFRESH_TOKEN,
)

auth.register_callback_handler(handler)

accounts = Account.fetch(auth)
account_managers: list[AccountManager] = []
for account in accounts:
    pot_manager = PotManager.from_account(auth, account)
    account_manager = AccountManager(auth, account, pot_manager, dry_run=False)
    account_manager.register_processor(PotMinimumProcessor(pot_manager))
    account_manager.register_processor(SavingsPercentageProcessor(pot_manager))
    account_manager.register_processor(PotGoalProcessor(pot_manager))
    account_manager.register_processor(SavingsOverflowProcessor(pot_manager))
    account_manager.register_processor(RoundupProcessor(pot_manager))
    account_managers.append(account_manager)

while 1:
    time.sleep(2)
    for account_manager in account_managers:
        logger.debug(f"optimizing account {account_manager}")
        account_manager.optimize_account()

