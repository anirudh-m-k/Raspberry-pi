from decimal import Decimal
from sqlalchemy import func
from app.extensions import db


class SettlementService:
    @staticmethod
    def get_member_balances(event_id):
        """Net balance per member: sum(paid) - sum(shares). Positive=creditor."""
        from app.models.event_expense import EventExpense
        from app.models.event_expense_split import EventExpenseSplit
        from app.models.event_member import EventMember

        members = EventMember.query.filter_by(event_id=event_id).all()
        balances = {}
        for member in members:
            paid = db.session.query(func.sum(EventExpense.amount)) \
                .filter(EventExpense.paid_by_member_id == member.id,
                        EventExpense.event_id == event_id).scalar() or 0
            share = db.session.query(func.sum(EventExpenseSplit.amount)) \
                .join(EventExpense, EventExpenseSplit.expense_id == EventExpense.id) \
                .filter(EventExpenseSplit.member_id == member.id,
                        EventExpense.event_id == event_id).scalar() or 0
            balances[member.id] = float(Decimal(str(paid)) - Decimal(str(share)))
        return balances

    @staticmethod
    def get_member_balances_with_names(event_id):
        """Get balances with member names."""
        from app.models.event_member import EventMember
        balances = SettlementService.get_member_balances(event_id)
        result = []
        for member_id, balance in balances.items():
            member = EventMember.query.get(member_id)
            if member:
                paid = db.session.query(func.sum(__import__('app.models.event_expense', fromlist=['EventExpense']).EventExpense.amount)) \
                    .filter_by(paid_by_member_id=member_id).scalar() or 0
                result.append({
                    'member_id': member_id,
                    'name': member.name,
                    'color': member.color,
                    'net_balance': round(balance, 2),
                    'paid': float(paid),
                })
        return result

    @staticmethod
    def calculate_settlements(event_id):
        """Greedy minimum-transaction algorithm. Matches largest debtor↔largest creditor."""
        balances = SettlementService.get_member_balances(event_id)
        creditors = sorted([(m, b) for m, b in balances.items() if b > 0.005], key=lambda x: -x[1])
        debtors = sorted([(m, -b) for m, b in balances.items() if b < -0.005], key=lambda x: -x[1])
        settlements = []
        ci, di = 0, 0
        while ci < len(creditors) and di < len(debtors):
            cm, cb = creditors[ci]
            dm, db_amt = debtors[di]
            amount = min(cb, db_amt)
            if amount > 0.005:
                settlements.append({
                    'from_member_id': dm,
                    'to_member_id': cm,
                    'amount': round(amount, 2)
                })
            creditors[ci] = (cm, round(cb - amount, 2))
            debtors[di] = (dm, round(db_amt - amount, 2))
            if creditors[ci][1] < 0.005:
                ci += 1
            if debtors[di][1] < 0.005:
                di += 1
        return settlements
