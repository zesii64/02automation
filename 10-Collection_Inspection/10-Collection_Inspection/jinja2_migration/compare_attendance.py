"""对比原始产物和 jinja2 版本的 agentPerformance 值."""
import json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

# 1. 从原始产物 HTML 中提取 REAL_DATA
html_path = Path(__file__).parent.parent / 'reports/Collection_Operations_Report_v3_6_2026-05-08.html'
html = html_path.read_text(encoding='utf-8')
m = re.search(r'REAL_DATA\s*=\s*(\{.*?\});', html, re.DOTALL)
if not m:
    print("ERROR: Could not find REAL_DATA in HTML")
    sys.exit(1)
orig_data = json.loads(m.group(1))
print(f"Original HTML: {len(orig_data.get('agentPerformance', {}))} groups")

# 2. build_context
from data_prep import build_context
BASE = Path(__file__).parent.parent
ctx = build_context(str(BASE / 'data/260318_output_automation_v3.xlsx'),
                    str(BASE / 'data/process_data_target.xlsx'))
print(f"Jinja2: {len(ctx.get('agentPerformance', {}))} groups")

# 3. 列出所有 group 名称
all_groups = sorted(set(list(orig_data.get('agentPerformance', {}).keys()) +
                        list(ctx.get('agentPerformance', {}).keys())))
print("\nAll groups in original:", list(orig_data.get('agentPerformance', {}).keys())[:10])
print("All groups in jinja2:", list(ctx.get('agentPerformance', {}).keys())[:10])

# 4. 对比 M1-Large A 和 S0- B Module
for group in ['M1-Large A', 'S0- B Module']:
    o_agents = {a['name']: a for a in orig_data.get('agentPerformance', {}).get(group, [])}
    j_agents = {a['name']: a for a in ctx.get('agentPerformance', {}).get(group, [])}
    print(f"\n=== {group} === (orig:{len(o_agents)} agents, j2:{len(j_agents)} agents)")

    all_names = sorted(set(o_agents.keys()) | set(j_agents.keys()))
    print(f"{'Agent':<25} {'Orig_attd':<10} {'J2_attd':<10} {'Orig_ach':<10} {'J2_ach':<10} {'Match':<8}")
    print("-" * 80)
    for name in all_names:
        o = o_agents.get(name, {})
        j = j_agents.get(name, {})
        o_att = o.get('attendance', 'MISSING')
        j_att = j.get('attendance', 'MISSING')
        o_ach = o.get('achievement', 'MISSING')
        j_ach = j.get('achievement', 'MISSING')
        att_match = "OK" if o_att == j_att else "DIFF"
        ach_match = "OK" if o_ach == j_ach else "DIFF"
        print(f"{name:<25} {str(o_att):<10} {str(j_att):<10} {str(o_ach):<10} {str(j_ach):<10} att={att_match} ach={ach_match}")

# 5. Daily attendance on 2026-04-29
selected_date = '2026-04-29'
print(f"\n=== Daily data on {selected_date} ===")
for group in ['M1-Large A', 'S0- B Module']:
    o_by_date = orig_data.get('agentPerformanceByDate', {}).get(group, {})
    j_by_date = ctx.get('agentPerformanceByDate', {}).get(group, {})
    agents = [k for k in o_by_date if selected_date in o_by_date[k]]
    print(f"\n-- {group}: {len(agents)} agents have data --")
    for name in agents[:8]:
        o_d = o_by_date[name].get(selected_date, {})
        j_d = j_by_date.get(name, {}).get(selected_date, {})
        print(f"  {name}: orig_attd={o_d.get('attendance')}, j2_attd={j_d.get('attendance')}, "
              f"orig_ach={o_d.get('achievement')}, j2_ach={j_d.get('achievement')}")

# 6. 检查 tlData 中 M1-Large A 的 days 数据
print("\n=== tlData.M1-Large A.days[2026-04-29] ===")
tl_day = None
for d in orig_data.get('tlData', {}).get('M1-Large A', {}).get('days', []):
    if d['date'] == '2026-04-29':
        tl_day = d
        break
if tl_day:
    print(f"  Original: target={tl_day.get('target')}, actual={tl_day.get('actual')}, achievement={tl_day.get('achievement')}, attendanceRate={tl_day.get('attendanceRate')}")

for d in ctx.get('tlData', {}).get('M1-Large A', {}).get('days', []):
    if d['date'] == '2026-04-29':
        print(f"  Jinja2:  target={d.get('target')}, actual={d.get('actual')}, achievement={d.get('achievement')}, attendanceRate={d.get('attendanceRate')}")
        break