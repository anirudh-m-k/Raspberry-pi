from flask import Blueprint, render_template, redirect, url_for

pages_bp = Blueprint('pages', __name__)


@pages_bp.route('/')
def landing():
    return render_template('auth/landing.html')


@pages_bp.route('/login')
def login():
    return render_template('auth/login.html')


@pages_bp.route('/register')
def register():
    return render_template('auth/register.html')


@pages_bp.route('/forgot-password')
def forgot_password():
    return render_template('auth/forgot_password.html')


@pages_bp.route('/dashboard')
def dashboard():
    return render_template('dashboard/index.html')


@pages_bp.route('/expenses')
def expenses():
    return render_template('expenses/index.html')


@pages_bp.route('/expenses/add')
def add_expense():
    return render_template('expenses/add.html')


@pages_bp.route('/expenses/<int:id>/edit')
def edit_expense(id):
    return render_template('expenses/edit.html')


@pages_bp.route('/income')
def income():
    return render_template('income/index.html')


@pages_bp.route('/income/add')
def add_income():
    return render_template('income/add.html')


@pages_bp.route('/income/<int:id>/edit')
def edit_income(id):
    return render_template('income/edit.html')


@pages_bp.route('/recurring')
def recurring():
    return render_template('recurring/index.html')


@pages_bp.route('/recurring/add')
def add_recurring():
    return render_template('recurring/add.html')


@pages_bp.route('/recurring/<int:id>/edit')
def edit_recurring(id):
    return render_template('recurring/edit.html')


@pages_bp.route('/budgets')
def budgets():
    return render_template('budgets/index.html')


@pages_bp.route('/budgets/add')
def add_budget():
    return render_template('budgets/add.html')


@pages_bp.route('/budgets/<int:id>')
def budget_detail(id):
    return render_template('budgets/detail.html')


@pages_bp.route('/budgets/<int:id>/edit')
def edit_budget(id):
    return render_template('budgets/edit.html')


@pages_bp.route('/goals')
def goals():
    return render_template('goals/index.html')


@pages_bp.route('/goals/add')
def add_goal():
    return render_template('goals/add.html')


@pages_bp.route('/goals/<int:id>')
def goal_detail(id):
    return render_template('goals/detail.html')


@pages_bp.route('/goals/<int:id>/edit')
def edit_goal(id):
    return render_template('goals/edit.html')


@pages_bp.route('/savings-pots')
def savings_pots():
    return render_template('savings-pots/index.html')


@pages_bp.route('/savings-pots/add')
def add_savings_pot():
    return render_template('savings-pots/add.html')


@pages_bp.route('/savings-pots/<int:id>')
def savings_pot_detail(id):
    return render_template('savings-pots/detail.html')


@pages_bp.route('/savings-pots/<int:id>/edit')
def edit_savings_pot(id):
    return render_template('savings-pots/edit.html')


@pages_bp.route('/accounts')
def accounts():
    return render_template('accounts/index.html')


@pages_bp.route('/accounts/add')
def add_account():
    return render_template('accounts/add.html')


@pages_bp.route('/accounts/<int:id>')
def account_detail(id):
    return render_template('accounts/detail.html')


@pages_bp.route('/accounts/<int:id>/edit')
def edit_account(id):
    return render_template('accounts/edit.html')


@pages_bp.route('/reports')
def reports():
    return render_template('reports/index.html')


@pages_bp.route('/calendar')
def calendar():
    return render_template('calendar/index.html')


@pages_bp.route('/notifications')
def notifications():
    return render_template('notifications/index.html')


@pages_bp.route('/settings')
def settings():
    return render_template('settings/index.html')


# Admin routes
@pages_bp.route('/admin')
def admin_dashboard():
    return render_template('admin/dashboard.html')


@pages_bp.route('/admin/users')
def admin_users():
    return render_template('admin/users.html')


@pages_bp.route('/admin/users/<user_id>')
def admin_user_detail(user_id):
    return render_template('admin/user_detail.html')


@pages_bp.route('/admin/audit')
def admin_audit():
    return render_template('admin/audit.html')


# ─── Events / Trip Planner Routes ───────────────────────────────────────────

@pages_bp.route('/events')
def events():
    return render_template('events/index.html')


@pages_bp.route('/events/create')
def create_event():
    return render_template('events/create.html')


@pages_bp.route('/events/join')
def join_event():
    return render_template('events/join.html')


@pages_bp.route('/events/<int:id>')
def event_detail(id):
    return render_template('events/detail.html', event_id=id)


@pages_bp.route('/events/<int:id>/group-details')
def event_group_details(id):
    return render_template('events/group_details.html', event_id=id)


@pages_bp.route('/events/<int:id>/expenses')
def event_expenses(id):
    return render_template('events/expenses.html', event_id=id)


@pages_bp.route('/events/<int:id>/expenses/add')
def event_add_expense(id):
    return render_template('events/expense_add.html', event_id=id)


@pages_bp.route('/events/<int:id>/expenses/<int:eid>/edit')
def event_edit_expense(id, eid):
    return render_template('events/expense_edit.html', event_id=id, expense_id=eid)


@pages_bp.route('/events/<int:id>/members')
def event_members(id):
    return render_template('events/members.html', event_id=id)


@pages_bp.route('/events/<int:id>/categories')
def event_categories(id):
    return render_template('events/categories.html', event_id=id)


@pages_bp.route('/events/<int:id>/settlements')
def event_settlements(id):
    return render_template('events/settlements.html', event_id=id)


@pages_bp.route('/events/<int:id>/analytics')
def event_analytics(id):
    return render_template('events/analytics.html', event_id=id)


@pages_bp.route('/events/<int:id>/sharing')
def event_sharing(id):
    return render_template('events/sharing.html', event_id=id)

