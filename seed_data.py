"""
Optional helper: create a demo user and load the sample holdings from
data/sample_data.csv, so you have a populated portfolio to demonstrate
immediately.

Usage:
    python seed_data.py

Creates (or reuses) the demo account:
    email:    demo@example.com
    password: demo1234

This is a convenience script for demonstrations. Every number the app
then displays is still calculated from this real database data -- the
seed script only inserts the holdings, it does not insert any
pre-computed results.
"""

import csv
import datetime
import os
import sys

from app import app
from config import Config
from database.database import db
from database.models import User, Holding, Transaction

DEMO_EMAIL = "demo@example.com"
DEMO_PASSWORD = "demo1234"


def main():
    with app.app_context():
        user = User.query.filter_by(email=DEMO_EMAIL).first()
        if user is None:
            user = User(name="Demo Student", email=DEMO_EMAIL)
            user.set_password(DEMO_PASSWORD)
            db.session.add(user)
            db.session.commit()
            print(f"Created demo user {DEMO_EMAIL} (password: {DEMO_PASSWORD})")
        else:
            print(f"Demo user {DEMO_EMAIL} already exists.")

        if Holding.query.filter_by(user_id=user.id).count() > 0:
            print("Demo user already has holdings. Nothing to do.")
            print("   (Delete database/portfolio.db and re-run to start fresh.)")
            return

        csv_path = os.path.join(Config.DATA_DIR, "sample_data.csv")
        if not os.path.exists(csv_path):
            print(f"ERROR: {csv_path} not found.")
            sys.exit(1)

        count = 0
        with open(csv_path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                holding = Holding(
                    user_id=user.id,
                    symbol=row["symbol"].strip().upper(),
                    asset_name=row["asset_name"].strip(),
                    asset_type=row["asset_type"].strip(),
                    sector=row["sector"].strip(),
                    quantity=float(row["quantity"]),
                    buy_price=float(row["buy_price"]),
                    purchase_date=datetime.datetime.strptime(row["purchase_date"], "%Y-%m-%d").date(),
                )
                db.session.add(holding)
                db.session.flush()

                db.session.add(Transaction(
                    user_id=user.id,
                    holding_id=holding.id,
                    transaction_type="BUY",
                    quantity=holding.quantity,
                    price=holding.buy_price,
                    transaction_date=holding.purchase_date,
                ))
                count += 1

        db.session.commit()
        print(f"Inserted {count} sample holdings for the demo user.")
        print("\nNow run:  python app.py")
        print(f"Then log in at http://127.0.0.1:5000/login with {DEMO_EMAIL} / {DEMO_PASSWORD}")


if __name__ == "__main__":
    main()
