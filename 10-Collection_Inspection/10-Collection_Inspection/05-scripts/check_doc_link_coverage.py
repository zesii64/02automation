"""诊断脚本：检查所有 group 的 module 映射及文档链接覆盖情况"""
import pandas as pd

BASE = r'd:/11automation/02automation/10-Collection_Inspection/10-Collection_Inspection'
EXCEL_PATH = BASE + r'/data/260318_output_automation_v3.xlsx'

def extract_module_key(group):
    g = group.strip()
    parts = g.split('-')
    if len(parts) >= 2:
        first_word = parts[1].strip().split()[0].lower() if parts[1].strip() else ''
        if first_word in ('large', 'small'):
            return f"{parts[0]}-{parts[1].strip().split()[0].capitalize()}"
    return parts[0]

tl_data = pd.read_excel(EXCEL_PATH, sheet_name='tl_data', engine='openpyxl')
tl_data['group_module'] = tl_data['group_id'].apply(extract_module_key)

print("=== tl_data['group_module'] unique values ===")
print(tl_data['group_module'].unique())

print("\n=== Each group_module contains group_ids ===")
for mod, grps in tl_data.groupby('group_module')['group_id'].apply(lambda x: sorted(x.unique())).items():
    print(f"\n{mod}: {grps}")

MODULE_IMPROVEMENT_PLAN_URL = {
    'S0': 'https://doc.weixin.qq.com/sheet/e3_AGIATAbTANsCNWcq1Hf0CS76ZJaSp',
    'S1': 'https://doc.weixin.qq.com/sheet/e3_AGIATAbTANsCNKGdG4MPaQreE00Ga',
    'S2': 'https://doc.weixin.qq.com/sheet/e3_AGIATAbTANsCNk6txUBU0SG2hZ9A0',
    'M1': 'https://doc.weixin.qq.com/sheet/e3_AGIATAbTANsCNs8XAuzKHQmq0m0W1'
}

print("\n=== Module doc-link coverage check ===")
all_modules_in_data = tl_data['group_module'].unique().tolist()
for mod in all_modules_in_data:
    has_url = mod in MODULE_IMPROVEMENT_PLAN_URL
    print(f"  {mod!r}: {'[YES]' if has_url else '[NO LINK]'}")

expected = {'S0', 'S1', 'S2', 'M1'}
unexpected = set(all_modules_in_data) - expected
if unexpected:
    print(f"\n=== UNEXPECTED MODULES (no doc link) ===")
    for u in sorted(unexpected):
        grps = sorted(tl_data[tl_data['group_module'] == u]['group_id'].unique())
        print(f"  {u}: {grps}")

print("\nDone.")
input("Press Enter to close...")
