import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def create_mock_data(filename="mock_data.xlsx"):
    print(f"Generating mock data: {filename} ...")
    
    # 1. Vintage Risk
    # Need: due_date, user_type, owing_principal, overdue_principal, period_no
    dates = pd.date_range(end=datetime.now(), periods=60)
    data = []
    
    user_types = ["新客", "老客", "存量老客"]
    
    for d in dates:
        for ut in user_types:
            # 100 rows per day per type
            base_vol = 100000 if ut == "新客" else 500000
            
            # Rate variation
            rate = 0.1
            if ut == "新客": rate = 0.2
            
            # Add some fluctuation
            if d.day % 5 == 0: rate += 0.05
            
            # Add trend (recent bad)
            if d > datetime.now() - timedelta(days=10):
                rate += 0.05
                
            owing = base_vol
            overdue = owing * rate
            
            # Additional columns for Term Matrix
            # period_no: 1~4, period_seq: 1/3/6
            product_combos = [(1, 1), (1, 3), (2, 3), (3, 3), (1, 6), (2, 6), (3, 6), (4, 6)]
            n_combos = len(product_combos)
            for p, ps in product_combos:
                # Split volume
                vol = owing / n_combos
                bad = overdue / n_combos
                
                row = {
                    "due_date": d,
                    "user_type": ut,
                    "period_no": p,
                    "period_seq": ps,
                    "mob": p,
                    "model_bin": np.random.choice(["A", "B", "C"]),
                    "owing_principal": vol,
                    "overdue_principal": bad,
                    "loan_cnt": 50,
                    "flag_principal": np.random.choice(["0-1000", "1000-2000", "2000-5000"])
                }
                
                # Mock d1..d31 columns
                for i in range(1, 32):
                    # Mock decay: d1 ~= overdue, d31 < overdue
                    # Just rough numbers
                    row[f"d{i}_principal"] = bad * (0.9 ** (i/10))
                    
                data.append(row)
                
    df_v = pd.DataFrame(data)
    
    # 2. Repay
    # natural_month, agent_bucket, group_name, repay_principal, start_owing_principal
    repay_data = []
    months = pd.period_range(end=datetime.now(), periods=3, freq='M')
    buckets = ["M1", "M2", "S1"]
    
    for m in months:
        m_str = m.strftime("%Y%m")
        for b in buckets:
            vol = 1000000
            rate = 0.8 if b == "S1" else 0.4
            
            repay_data.append({
                "natural_month": m_str,
                "agent_bucket": b,
                "group_name": f"{b}_Group_A",
                "owner_id": "Op1",
                "start_owing_principal": vol,
                "repay_principal": vol * rate,
                "case_bucket": b
            })
            
    df_r = pd.DataFrame(repay_data)
    
    # 3. Process
    df_p = pd.DataFrame([{
        "natural_month": datetime.now().strftime("%Y%m"),
        "owner_bucket": "M1",
        "owner_group": "M1_Group_A",
        "cover_rate": 0.9,
        "case_connect_rate": 0.2,
        "call_times_avg": 50,
        "raw_owing_case_cnt": 1000,
        "raw_uncomm_case_cnt": 100,
        "raw_call_times": 5000,
        "raw_call_connect_times": 1000
    }])

    with pd.ExcelWriter(filename) as writer:
        df_v.to_excel(writer, sheet_name="vintage_risk", index=False)
        df_r.to_excel(writer, sheet_name="natural_month_repay", index=False)
        df_p.to_excel(writer, sheet_name="process_data", index=False)
        
    print("Mock data generated.")

if __name__ == "__main__":
    create_mock_data()
