DEFAULT_EXPENSE_CATEGORIES = [
    {'name': 'Food & Dining', 'icon': 'utensils', 'color': '#ef4444'},
    {'name': 'Groceries', 'icon': 'shopping-cart', 'color': '#22c55e'},
    {'name': 'Transport', 'icon': 'car', 'color': '#3b82f6'},
    {'name': 'Shopping', 'icon': 'shopping-bag', 'color': '#ec4899'},
    {'name': 'Bills & Utilities', 'icon': 'zap', 'color': '#f59e0b'},
    {'name': 'Healthcare', 'icon': 'heart-pulse', 'color': '#06b6d4'},
    {'name': 'Entertainment', 'icon': 'film', 'color': '#a855f7'},
    {'name': 'Other', 'icon': 'more-horizontal', 'color': '#94a3b8'},
]

DEFAULT_INCOME_CATEGORIES = [
    {'name': 'Salary', 'icon': 'briefcase', 'color': '#22c55e'},
    {'name': 'Freelance', 'icon': 'laptop', 'color': '#3b82f6'},
    {'name': 'Business', 'icon': 'building-2', 'color': '#8b5cf6'},
    {'name': 'Investments', 'icon': 'trending-up', 'color': '#f59e0b'},
    {'name': 'Rental', 'icon': 'key', 'color': '#06b6d4'},
    {'name': 'Gifts', 'icon': 'gift', 'color': '#ec4899'},
    {'name': 'Refunds', 'icon': 'rotate-ccw', 'color': '#6366f1'},
    {'name': 'Other', 'icon': 'more-horizontal', 'color': '#94a3b8'},
]

DEFAULT_RECURRING_CATEGORIES = [
    {'name': 'Rent', 'icon': 'home', 'color': '#8b5cf6'},
    {'name': 'Subscriptions', 'icon': 'repeat', 'color': '#a855f7'},
    {'name': 'Insurance', 'icon': 'shield', 'color': '#3b82f6'},
    {'name': 'EMI / Loan', 'icon': 'landmark', 'color': '#ef4444'},
    {'name': 'Utilities', 'icon': 'zap', 'color': '#f59e0b'},
    {'name': 'Salary', 'icon': 'briefcase', 'color': '#22c55e'},
    {'name': 'SIP / Investment', 'icon': 'trending-up', 'color': '#06b6d4'},
    {'name': 'Other', 'icon': 'more-horizontal', 'color': '#94a3b8'},
]

DEFAULT_EVENT_CATEGORIES = [
    {'name': 'Accommodation', 'icon': 'home', 'color': '#8b5cf6'},
    {'name': 'Food & Dining', 'icon': 'utensils', 'color': '#f59e0b'},
    {'name': 'Transport', 'icon': 'car', 'color': '#3b82f6'},
    {'name': 'Activities', 'icon': 'zap', 'color': '#22c55e'},
    {'name': 'Shopping', 'icon': 'shopping-bag', 'color': '#ec4899'},
    {'name': 'Drinks & Nightlife', 'icon': 'wine', 'color': '#a855f7'},
    {'name': 'Fuel', 'icon': 'fuel', 'color': '#ef4444'},
    {'name': 'Medical', 'icon': 'heart-pulse', 'color': '#06b6d4'},
    {'name': 'Miscellaneous', 'icon': 'more-horizontal', 'color': '#94a3b8'},
]

EVENT_STATUSES = ['planning', 'active', 'completed', 'archived']
SPLIT_TYPES = ['equal', 'custom', 'percentage']

PAYMENT_METHODS = [
    'Cash',
    'Credit Card',
    'Debit Card',
    'UPI',
    'Net Banking',
    'Wallet',
    'Bank Transfer',
]

ACCOUNT_TYPES = [
    'cash',
    'bank',
    'credit_card',
    'upi',
    'wallet',
    'investment',
]

RECURRING_FREQUENCIES = [
    'daily',
    'weekly',
    'monthly',
    'quarterly',
    'yearly',
]

GOAL_PRIORITIES = [
    'low',
    'medium',
    'high',
]

BUDGET_PERIODS = [
    'weekly',
    'monthly',
]