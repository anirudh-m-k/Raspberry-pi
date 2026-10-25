# Finance-Track Application Development Prompt

## 1. Overview
The goal is to develop a personal finance management web application that helps a single user answer primary financial questions such as:
- What did I spend today?
- Where is my money going?
- How much did I save this month?
- What recurring expenses are draining my finances?
- Can I afford my goal?
- How much money will I have next month?
- Which category overspends most?

**User Role:** Single User

---

## 2. Full Application Architecture

### Authentication Module
* **Landing Page (Public):**
  * First impression & app overview.
  * **Features:** Hero section, App benefits, Feature highlights, Screenshots, Testimonials, CTA buttons (Register, Login), Dark/light mode toggle.
  * **Design:** Responsive design with a premium, minimal aesthetic. Should NOT look like an AI-generated template design.
* **Registration Page:**
  * **Features:** Name, Email, Password, Confirm Password, Password strength checker, Email OTP verification (verify on the same page without changing the URL path), Terms acceptance.
  * **Security:** Password hashing (bcrypt), Email verification token, CSRF protection, Rate limiting.
* **Login Page:**
  * **Features:** Email/Username, Password, Remember me, Forgot password, Device recognition.
  * **Security:** Flask-Login / JWT Bearer token, Session management.

### Main Application Structure (Sidebar Navigation)
**Main Sections:** Dashboard, Expenses, Income, Recurring Transactions, Budgets, Goals, Savings Pot, Accounts, Reports, Calendar, Notifications, Settings.

#### Dashboard Page
Provide a complete financial snapshot.
* **Top Cards:** Total Balance, Today’s Expenses, Today’s Income, Monthly Expenses, Monthly Income, Savings Rate, Savings Pot Balance, Goal Progress.
* **Visual Charts:** Expense by category (Pie Chart), Income sources (Bar Chart), Weekly spend trend (Line Chart), Monthly comparison, Cashflow graph, Goal contribution graph, Savings pot contribution graph.
* **Smart Insights:** Provide actionable insights like: “You spent 30% more on food this week”, “Your travel expense increased”, “Upcoming EMI in 3 days”, “Goal completion in 2 months”.
* **Quick Actions:** Add Expense, Add Income, Add Goal, Transfer to Goal, Add Budget.

#### Expense Management Page
* **Core Features:** Add Expense (Amount, Category, Subcategory, Date, Time, Payment method, Account source (optional), Merchant/vendor (optional), Notes).
* **Main Categories:** *[Need option to add custom categories in Settings page]* Food & Dining, Groceries, Travel, Fuel, Rent, Utilities, Shopping, Entertainment.
* **Functionalities:** Edit/Delete, Search, Filter by (Date, Category, Amount, Payment type), Sort, Duplicate transaction.

#### Income Management Page
* **Core Features:** Add Income (Amount, Source, Category, Date, Payment method, Notes). *[Need option to add custom categories in Settings page]* (e.g., Salary, Freelance, Business, Rental, Passive income).
* **Extra Features:** Salary breakdown, Monthly recurring salary, Income growth graph.

#### Recurring Transactions Page
Automate recurring financial events.
* **Expense Recurring:** *[Need option to add custom categories in Settings page]* EMI, Rent, SIP, Insurance, Subscription, Loan, Utility bills.
* **Income Recurring:** Salary, Rent received, Dividends, Pension.
* **Features:** Frequency (Daily, Weekly, Monthly, Quarterly, Yearly), Start date, End date, Auto-add transaction, Skip option, Pause recurring, Reminder before due date, Auto notifications.

#### Budget Page
Control category spending.
* **Features:** Monthly budget, Weekly budget, Category-specific budget, Budget alerts, Overspending warning, Budget utilization %, Auto-adjust based on trends.
* **Example:** Food budget = ₹8,000/month, Spent = ₹6,200, Remaining = ₹1,800.

#### Goals / Savings Page
* **Goals:** *[Want Custom Add option]* Examples: Vacation, Emergency fund, Birthday, Wedding.
  * **Features:** Goal title, Target amount, Deadline, Priority, Auto-save contribution, Manual contribution, Goal progress bar, Goal analytics (“How much per month needed”).
  * **Cool Additions:** Goal image, Motivational tracker, Milestones.
  * **Concept:** Target amount required, deadline optional, completion tracking.
* **Savings Pot:** *[Want Custom Add option]* Examples: Emergency Fund, Rainy Day Fund, Shopping Reserve, Medical Backup, Festival Expenses, Car Maintenance, Home Expenses, Child Education Reserve, Investment Opportunity Fund, Gift Fund.
  * **Concept:** No target required, no deadline, add/withdraw anytime, flexible financial bucket.

#### Accounts Page
* **Manage:** Cash, Bank accounts, Credit cards, UPI, Wallets, Investments.
* **Features:** Balance tracking, Transfers, Account history, Reconciliation, Hidden accounts.

#### Calendar View
* **Purpose:** Visual timeline.
* **Shows:** Daily expenses, Salary day, EMI due, Goal deadlines, Bills, Subscription renewals.

#### Reports & Analytics Page
* **Reports:** Daily, Weekly, Monthly, Yearly.
* **Advanced Insights [Required]:** Spending heatmap, Category comparison, Income vs expense, Savings ratio, Investment trends.
* **Export:** PDF, Excel, CSV.

#### Notifications System
* **Alerts:** EMI due, Subscription renew, Salary credited, Budget exceeded, Goal reminder, Weekly summary, Monthly summary.

#### Settings Page
* **Features:** Profile management, Currency, Timezone, Theme, Security settings, Password change, Add custom categories for (Expense, Income, Recurring), Data export, Data deletion, Backup/restore.

---

## 3. Security Implementation
* **Must Have:** bcrypt password hashing, CSRF protection for state-changing endpoints, Session timeout, Encrypted sensitive fields.
* **Audit Logs:** Logs of creation, deletion, and updation *[Only sensitive logs required; omit unnecessary logs]*.
* **Secure Headers & HTTPS.**
* **Backup Mechanisms.**

---

## 4. Database Structure
**Suggested Entities (Generate proper schemas and relationships based on requirements):**
* `users`
* `expenses`
* `income`
* `recurring_transactions`
* `budgets`
* `goals`
* `goal_contributions`
* `savings_pots`
* `notifications`
* `accounts`
* `categories`
* `settings`
* `reports_cache`
* `audit_logs`

---

## 5. Tech Stack
* **Backend:** Flask, Flask-Login, Flask-WTF, SQLAlchemy, Alembic, Celery/APScheduler, bcrypt.
* **Frontend:** HTML, CSS, Bootstrap/Tailwind, JavaScript, Chart.js / ApexCharts.
* **Database:** SQLite.

---

## 6. UI/UX Requirements
* **Design Aesthetic:** Premium modern dashboard with a minimal design approach.
* **Mode:** Native Dark mode support.
* **Responsiveness:** Strictly adaptable for mobile responsive views.
* **Components:** Card-based layouts, Animated charts, Minimalist icons, Quick entry forms.

---

## 7. Strict AI Execution Instructions
Strictly follow these instructions during development:
1. **Planning:** Create a proper plan for the development of the application.
2. **Implementation File:** Create an `Implementation.md` file detailing the proper implementation plan phases and the features needed to be implemented in each phase with checkmarks (`- [ ]`) for each one. After completion of an implementation phase/feature, check that feature in the file (`- [x]`).
3. **Logging:** Create a `logs.md` file for logging all the actions done while developing the application.
4. **Prompt Reference:** Refer to this `prompt.md` file constantly to avoid straying from the context and requirements while developing.
5. **General Execution:** Add any other necessary components, configurations, or best practices required for smooth implementation.
