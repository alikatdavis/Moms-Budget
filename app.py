import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
from github import Github
import calendar
import io

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="FedPay Budget Pro", page_icon="💰", layout="wide")

# --- CONNECT TO GITHUB ---
# We use st.secrets so your token isn't exposed in the code
if "GITHUB_TOKEN" not in st.secrets or "REPO_NAME" not in st.secrets:
    st.error("⚠️ Secrets Missing!")
    st.info("You need to add GITHUB_TOKEN and REPO_NAME to your Streamlit Cloud Secrets.")
    st.stop()

try:
    g = Github(st.secrets["GITHUB_TOKEN"])
    repo_name = st.secrets["REPO_NAME"]
    repo = g.get_repo(repo_name)
except Exception as e:
    st.error("⚠️ Security Connection Failed!")
    st.info(f"Error details: {e}")
    st.stop()

# --- HELPER FUNCTIONS ---
def save_to_github(filename, content):
    try:
        try:
            contents = repo.get_contents(filename)
            repo.update_file(contents.path, f"Update {filename}", content, contents.sha)
        except:
            repo.create_file(filename, f"Create {filename}", content)
        return True
    except Exception as e:
        st.error(f"Error saving: {e}")
        return False

def load_from_github(filename):
    try:
        file_content = repo.get_contents(filename)
        return pd.read_csv(io.StringIO(file_content.decoded_content.decode()))
    except:
        return None

def get_saved_months():
    try:
        files = repo.get_contents("")
        saved = [f.name for f in files if f.name.endswith(".csv") and "Budget_" in f.name]
        return saved
    except:
        return []

def load_last_month_data():
    files = get_saved_months()
    if not files: return None
    
    def parse_filename(f):
        try:
            date_str = f.replace("Budget_", "").replace(".csv", "")
            return datetime.strptime(date_str, "%b_%Y")
        except:
            return datetime.min 
            
    files.sort(key=parse_filename, reverse=True)
    latest_file = files[0]
    
    df = load_from_github(latest_file)
    if df is not None:
        df = df.fillna(0)
        
        if 'frequency' not in df.columns:
            df['frequency'] = 'Monthly'
        else:
            df['frequency'] = df['frequency'].fillna('Monthly')
            
        if 'annual_month' not in df.columns:
            df['annual_month'] = 0
            
        if not df.empty and 'meta_pay_date' in df.columns:
            try:
                st.session_state['restored_date'] = pd.to_datetime(df.iloc[0]['meta_pay_date']).date()
                st.session_state['restored_pay_0'] = float(df.iloc[0].get('meta_inc_pay_0', 2449.0))
                st.session_state['restored_rent_0'] = float(df.iloc[0].get('meta_inc_rent_0', 2100.0))
                st.session_state['restored_other_0'] = float(df.iloc[0].get('meta_inc_other_0', 0.0))
                st.session_state['restored_pay_1'] = float(df.iloc[0].get('meta_inc_pay_1', 2449.0))
                st.session_state['restored_rent_1'] = float(df.iloc[0].get('meta_inc_rent_1', 0.0))
            except:
                pass
        
        cols_to_keep = ['name', 'amount', 'category', 'due_day', 'frequency', 'annual_month']
        actual_cols = [c for c in cols_to_keep if c in df.columns]
        return df[actual_cols].to_dict('records')
        
    return None

# --- CALLBACKS ---
def update_bill_amount(index, key_name):
    new_value = st.session_state[key_name]
    st.session_state.bills[index]['amount'] = new_value

def update_bill_day(index, key_name):
    new_value = st.session_state[key_name]
    st.session_state.bills[index]['due_day'] = int(new_value)

# --- SNOWBALL ENGINE ---
def calculate_snowball(debts_data, extra_payment):
    debts = sorted(debts_data, key=lambda x: x['Balance'])
    schedule = []
    current_date = datetime.now()
    months_passed = 0
    import copy
    debts = copy.deepcopy(debts)
    
    while any(d['Balance'] > 0 for d in debts):
        months_passed += 1
        current_date += relativedelta(months=1)
        month_str = current_date.strftime("%b %Y")
        monthly_budget = extra_payment
        
        for d in debts:
            if d['Balance'] > 0:
                interest = (d['Balance'] * (d['APR'] / 100)) / 12
                d['Balance'] += interest
                payment = min(d['Balance'], d['Min Payment'])
                d['Balance'] -= payment
                if d['Balance'] <= 0:
                    monthly_budget += d['Min Payment']
                    d['Balance'] = 0
        
        for d in debts:
            if d['Balance'] > 0:
                attack_payment = min(d['Balance'], monthly_budget)
                d['Balance'] -= attack_payment
                monthly_budget -= attack_payment
                if monthly_budget <= 0: break
        
        total_balance = sum(d['Balance'] for d in debts)
        schedule.append({"Month": month_str, "Remaining Debt": total_balance})
        if months_passed > 360: break
            
    return schedule, current_date

# --- APP NAVIGATION ---
st.sidebar.title("📅 Budget Timeline")
saved_files = get_saved_months()
mode = st.sidebar.radio("View Mode:", ["Current (Live)", "Debt Snowball Tool ☃️", "History Archive"])

if mode == "History Archive":
    if not saved_files:
        st.sidebar.warning("No saved months yet.")
    else:
        selected_file = st.sidebar.selectbox("Select Month to View", saved_files)
        if selected_file:
            st.title(f"📂 Archive: {selected_file}")
            df_history = load_from_github(selected_file)
            st.dataframe(df_history, use_container_width=True)
            st.stop() 

# --- INITIALIZE BILLS ---
def get_default_bills():
    return [
        {"name": "Mortgage", "amount": 1772, "category": "HOUSING", "due_day": 1, "frequency": "Monthly", "annual_month": 0},
        {"name": "Rent", "amount": 1200, "category": "HOUSING", "due_day": 15, "frequency": "Monthly", "annual_month": 0},
        {"name": "Electricity", "amount": 346, "category": "HOUSING", "due_day": 12, "frequency": "Monthly", "annual_month": 0},
        {"name": "Lowes", "amount": 54, "category": "Loans", "due_day": 20, "frequency": "Monthly", "annual_month": 0},
        {"name": "AT&T Phone", "amount": 100, "category": "PHONE", "due_day": 26, "frequency": "Monthly", "annual_month": 0},
        {"name": "AT&T Internet - Home", "amount": 100, "category": "Internet", "due_day": 26, "frequency": "Monthly", "annual_month": 0},
        {"name": "AT&T Internet - Nick", "amount": 100, "category": "Internet", "due_day": 26, "frequency": "Monthly", "annual_month": 0},
        {"name": "AT&T Internet", "amount": 36, "category": "ENTERTAINMENT", "due_day": 14, "frequency": "Monthly", "annual_month": 0},
        {"name": "Klarna", "amount": 108, "category": "LOANS", "due_day": 13, "frequency": "Monthly", "annual_month": 0},
        {"name": "Avant", "amount": 125, "category": "LOANS", "due_day": 28, "frequency": "Monthly", "annual_month": 0},
        {"name": "Car Insurance - Me", "amount": 100, "category": "Insurance", "due_day": 26, "frequency": "Monthly", "annual_month": 0},
        {"name": "Car Insurance - Mom", "amount": 100, "category": "Insurance", "due_day": 26, "frequency": "Monthly", "annual_month": 0},
        {"name": "Car Insurance - Ny", "amount": 100, "category": "Insurance", "due_day": 26, "frequency": "Monthly", "annual_month": 0},
    ]

if 'bills' not in st.session_state:
    last_month = load_last_month_data()
    if last_month:
        st.session_state.bills = last_month
        st.toast("✅ Loaded from history!", icon="🔄")
    else:
        st.session_state.bills = get_default_bills()

# --- SNOWBALL UI ---
if mode == "Debt Snowball Tool ☃️":
    st.title("☃️ Debt Snowball Calculator")
    if 'debt_data' not in st.session_state:
        st.session_state.debt_data = [{"Debt Name": "Credit Card 1", "Balance": 500.0, "APR (%)": 20.0, "Min Payment": 25.0}]

    col1, col2 = st.columns([2, 1])
    with col1:
        st.subheader("1. Enter Your Debts")
        if st.button("📥 Import LOANS from Budget"):
            loans = [b for b in st.session_state.bills if str(b['category']).upper() == "LOANS"]
            for loan in loans:
                new_entry = {"Debt Name": loan['name'], "Balance": 0.0, "APR (%)": 0.0, "Min Payment": float(loan['amount'])}
                if not any(d['Debt Name'] == loan['name'] for d in st.session_state.debt_data):
                    st.session_state.debt_data.append(new_entry)
            st.rerun()

        edited_debts = st.data_editor(st.session_state.debt_data, num_rows="dynamic", use_container_width=True, key="debt_editor")
        st.session_state.debt_data = edited_debts

    with col2:
        st.subheader("2. Your Strategy")
        extra_cash = st.number_input("Extra Monthly Payment ($)", value=100.0, step=50.0)

    st.divider()
    if st.button("🚀 Calculate Freedom Date", type="primary"):
        calc_data = [row for row in st.session_state.debt_data if row['Balance'] > 0]
        if not calc_data:
            st.warning("Enter at least one debt with a balance > 0.")
        else:
            schedule, end_date = calculate_snowball(calc_data, extra_cash)
            st.balloons()
            c1, c2, c3 = st.columns(3)
            with c1: st.metric("Debt Free Date", end_date.strftime("%B %Y"))
            with c2: st.metric("Total Debt", f"${sum(d['Balance'] for d in calc_data):,.0f}")
            with c3: st.metric("Time to Freedom", f"{len(schedule)} Months")
            st.line_chart(pd.DataFrame(schedule).set_index("Month"))
    st.stop()

# --- MAIN BUDGET UI ---
with st.sidebar:
    st.divider()
    with st.expander("➕ Quick Add Bill"):
        with st.form("add_bill_form"):
            new_name = st.text_input("Bill Name")
            new_amount = st.number_input("Amount ($)", min_value=0.0, step=1.0)
            new_cat = st.selectbox("Category", ["HOUSING", "LOANS", "ENTERTAINMENT", "SAVINGS", "OTHER"])
            new_day = st.number_input("Due Day", 1, 31, 1)
            freq_val = st.selectbox("Frequency", ["Monthly", "Every 2 Weeks", "Annual"])
            annual_month_val = 0
            if freq_val == "Annual":
                annual_month_val = st.selectbox("Month Due", range(1, 13), format_func=lambda x: datetime(2023, x, 1).strftime("%B"))
            if st.form_submit_button("Add Bill") and new_name:
                st.session_state.bills.append({"name": new_name, "amount": new_amount, "category": new_cat, "due_day": int(new_day), "frequency": freq_val, "annual_month": int(annual_month_val)})
                st.rerun()

    with st.expander("🗑️ Delete a Bill"):
        if st.session_state.bills:
            to_del = st.selectbox("Select Bill", [b['name'] for b in st.session_state.bills])
            if st.button("❌ Delete"):
                st.session_state.bills = [b for b in st.session_state.bills if b['name'] != to_del]
                st.rerun()

    st.divider()
    if st.button("⚠️ Reset to Defaults"):
        st.session_state.bills = get_default_bills()
        st.rerun()
    
    current_month_name = st.text_input("Month Name", value=datetime.now().strftime("Budget_%b_%Y"))
    pay_date_1 = st.date_input("First Pay Date", st.session_state.get('restored_date', datetime.now()))
    pay_date_1 = datetime.combine(pay_date_1, datetime.min.time())
    pay_date_2 = pay_date_1 + timedelta(weeks=2)
    pay_date_3 = pay_date_1 + timedelta(weeks=4)
    show_3 = st.checkbox("Force 3-Paycheck View", value=False) or (pay_date_1.month == pay_date_3.month)
    
    st.divider()
    if st.button("💾 Save & Close Month"):
        df_save = pd.DataFrame(st.session_state.bills)
        df_save['meta_pay_date'] = pay_date_1
        for i in range(2):
            df_save[f'meta_inc_pay_{i}'] = st.session_state.get(f'pay_{i}', 2449.0)
            df_save[f'meta_inc_rent_{i}'] = st.session_state.get(f'rent_{i}', 0.0) if i == 0 else 0
            df_save[f'meta_inc_other_{i}'] = st.session_state.get(f'other_{i}', 0.0)
        
        filename = f"{current_month_name}.csv"
        with st.spinner("Saving..."):
            if save_to_github(filename, df_save.to_csv(index=False)):
                st.success(f"Saved {filename}!")
                st.balloons()

st.title("📊 Current Budget")
cols = st.columns(3 if show_3 else 2)
pay_periods = [pay_date_1, pay_date_2]
if show_3: pay_periods.append(pay_date_3)

for i, p_date in enumerate(pay_periods):
    p_num = i + 1
    p_end = p_date + timedelta(days=13)
    with cols[i]:
        st.header(f"Pay #{p_num}")
        st.caption(f"{p_date.strftime('%b %d')} - {p_end.strftime('%b %d')}")
        
        with st.expander("💸 Income", expanded=False):
            val_pay = st.session_state.get(f'restored_pay_{i}', 2449.0)
            val_rent = st.session_state.get(f'restored_rent_{i}', 2100.0 if p_num == 1 else 0.0)
            val_other = st.session_state.get(f'restored_other_{i}', 0.0)
            in_pay = st.number_input("Pay", value=val_pay, step=50.0, key=f"pay_{i}")
            in_rent = st.number_input("Rent", value=val_rent, step=50.0, key=f"rent_{i}")
            in_other = st.number_input("Other", value=val_other, step=10.0, key=f"other_{i}")
            income = in_pay + in_rent + in_other

        st.markdown(f"**Income:** :green[${income:,.0f}]")
        st.markdown("---")
        
        period_bills = []
        for idx, bill in enumerate(st.session_state.bills):
            freq = bill.get('frequency', 'Monthly')
            include = False
            if freq == 'Every 2 Weeks': include = True
            elif freq == 'Annual': 
                if p_date.month == int(bill.get('annual_month', 0)) or p_end.month == int(bill.get('annual_month', 0)): include = True
            else:
                d = bill['due_day']
                if (p_date.day < p_end.day and p_date.day <= d < p_end.day) or \
                   (p_date.day > p_end.day and (d >= p_date.day or d < p_end.day)): include = True
            
            if include: period_bills.append(idx)

        total_bills = 0
        if not period_bills: st.info("No bills")
        else:
            for idx in period_bills:
                b = st.session_state.bills[idx]
                k_amt = f"b_amt_{idx}_{p_num}"
                k_day = f"b_day_{idx}_{p_num}"
                c1, c2 = st.columns([3, 1])
                with c1: st.number_input(b['name'], value=float(b['amount']), step=1.0, key=k_amt, on_change=update_bill_amount, args=(idx, k_amt))
                with c2: st.number_input("Due", value=int(b['due_day']), min_value=1, max_value=31, key=k_day, on_change=update_bill_day, args=(idx, k_day))
                total_bills += st.session_state.bills[idx]['amount']

        st.markdown("---")
        res = income - total_bills
        st.write(f"**Bills:** ${total_bills:,.2f}")
        if res > 0: st.success(f"**Left:** ${res:,.2f}")
        else: st.error(f"**Short:** ${res:,.2f}")
