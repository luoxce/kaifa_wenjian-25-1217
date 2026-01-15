import sqlite3
import pandas as pd
import json
import os

# 数据库路径 (根据 .env 配置)
DB_PATH = 'data/alpha_arena.db'

def check_latest_run():
    if not os.path.exists(DB_PATH):
        print(f"❌ 错误: 找不到数据库文件 {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # 允许通过列名访问
    cursor = conn.cursor()

    try:
        print("🔍 正在查询最新的一次回测记录...")

        # 1. 查 backtest_results (总表)
        cursor.execute("SELECT * FROM backtest_results ORDER BY created_at DESC LIMIT 1")
        result = cursor.fetchone()
        
        if not result:
            print("⚠️ 数据库中没有任何回测结果。请先运行 scripts/run_backtest_mvp.py")
            return

        run_id = result['run_id']
        print(f"\n✅ 找到最新回测 ID: {run_id}")
        print(f"   策略: {result['strategy_name']}")
        print(f"   时间范围: {result['start_time']} -> {result['end_time']}")
        print(f"   总收益率: {result['total_return']}%")
        print(f"   最大回撤: {result['max_drawdown']}%")

        # 2. 查 backtest_orders (订单表)
        df_orders = pd.read_sql_query(f"SELECT * FROM backtest_orders WHERE run_id = '{run_id}'", conn)
        print(f"\n📦 关联订单数: {len(df_orders)}")
        if not df_orders.empty:
            print(f"   买入: {len(df_orders[df_orders['side'] == 'BUY'])} | 卖出: {len(df_orders[df_orders['side'] == 'SELL'])}")
            print(f"   状态分布: {df_orders['status'].value_counts().to_dict()}")

        # 3. 查 backtest_decisions (决策表 - 验证 Signal Payload)
        df_decisions = pd.read_sql_query(f"SELECT * FROM backtest_decisions WHERE run_id = '{run_id}' LIMIT 1", conn)
        print(f"\n🧠 关联决策记录数: (查询中...)")
        cursor.execute(f"SELECT count(*) FROM backtest_decisions WHERE run_id = '{run_id}'")
        decision_count = cursor.fetchone()[0]
        print(f"   共记录决策: {decision_count} 条")
        
        if not df_decisions.empty:
            raw_signal = df_decisions.iloc[0]['signal_data']
            print("   [示例] 第一条决策原始数据片段:")
            try:
                # 尝试解析 JSON 打印前 100 字符
                print(f"   {raw_signal[:100]}...") 
            except:
                print("   无法解析 JSON")

        # 4. 查 order_lifecycle_events (生命周期表)
        # 这一步验证生命周期管理器是否介入
        print(f"\n🔄 生命周期事件检查:")
        if not df_orders.empty:
            sample_order_id = df_orders.iloc[0]['order_id']
            df_events = pd.read_sql_query(f"SELECT * FROM order_lifecycle_events WHERE order_id = '{sample_order_id}'", conn)
            print(f"   订单 {sample_order_id} 的状态流转: {len(df_events)} 次变更")
            for _, row in df_events.iterrows():
                print(f"     - {row['from_status']} -> {row['to_status']} ({row['event_type']})")
        else:
            print("   没有订单，无法检查生命周期。")

    except Exception as e:
        print(f"❌ 查询出错: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    check_latest_run()