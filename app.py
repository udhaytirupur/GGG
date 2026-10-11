import streamlit as st
import sqlite3
import pandas as pd
from dataclasses import dataclass
from typing import Dict, Any

# ==========================================
# 1. PAGE CONFIGURATION & CSS
# ==========================================
st.set_page_config(page_title="Funded Hedge AI Pro", layout="wide", initial_sidebar_state="collapsed")

# Advanced CSS to force perfect UI formatting, fix button colors, and handle light/dark mode clashes
st.markdown("""
<style>
    /* Force the entire background to be dark so it always looks professional */
    .stApp { background-color: #0E1117 !important; color: #FAFAFA !important; }
    
    /* Make buttons thick and bold */
    div.stButton > button { height: 60px; border-radius: 8px; }
    
    /* 1. EVAL WINS Button (Light Green) */
    div[data-testid="column"]:nth-of-type(2) div[data-testid="stHorizontalBlock"] div[data-testid="column"]:nth-of-type(1) button {
        background-color: #A5D6A7 !important; 
        color: #000000 !important;
        border: 2px solid #2E7D32 !important;
        font-size: 18px !important;
        font-weight: bold !important;
    }
    
    /* 2. EVAL LOSES Button (Light Red) */
    div[data-testid="column"]:nth-of-type(2) div[data-testid="stHorizontalBlock"] div[data-testid="column"]:nth-of-type(2) button {
        background-color: #EF9A9A !important; 
        color: #000000 !important;
        border: 2px solid #C62828 !important;
        font-size: 18px !important;
        font-weight: bold !important;
    }
    
    /* 3. RESET ALL DATA Button (Light Red) */
    div[data-testid="column"]:nth-of-type(2) > div.element-container:last-of-type button {
        background-color: #EF9A9A !important; 
        color: #000000 !important;
        border: 2px solid #C62828 !important;
        font-size: 16px !important;
        font-weight: bold !important;
    }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 2. AI OPTIMIZER & STATE
# ==========================================
@dataclass
class TradeState:
    eval_balance: float
    eval_target: float
    eval_dd_limit: float
    broker_balance: float
    futures_lot: float
    sl_points: float
    tp_points: float
    eval_sequence: str = ""
    base_broker_lot: float = 0.04
    trade_number: int = 1
    scale_factor: float = 1.0

class SequenceOptimizer:
    def __init__(self):
        self.sequence_map = {
            "LL": [0.04, 0.08],
            "LWWW": [0.04, 0.08, 0.08, 0.24],
            "LWWLL": [0.04, 0.08, 0.08, 0.24, 0.08],
            "LWWLWW": [0.04, 0.08, 0.08, 0.24, 0.08, 0.32],
            "LWWLWLW": [0.04, 0.08, 0.08, 0.24, 0.08, 0.32, 0.16],
            "LWWLWLL": [0.04, 0.08, 0.08, 0.24, 0.08, 0.32, 0.16],
            "LWLL": [0.04, 0.08, 0.08, 0.08],
            "LWLWWW": [0.04, 0.08, 0.08, 0.08, 0.08, 0.42],
            "LWLWWLL": [0.04, 0.08, 0.08, 0.08, 0.08, 0.42, 0.16],
            "LWLWWLW": [0.04, 0.08, 0.08, 0.08, 0.08, 0.42, 0.16],
            "LWLWLL": [0.04, 0.08, 0.08, 0.08, 0.08, 0.08],
            "LWLWLWW": [0.04, 0.08, 0.08, 0.08, 0.08, 0.08, 0.08],
            "LWLWLWLL": [0.04, 0.08, 0.08, 0.08, 0.08, 0.08, 0.08, 0.02],
            "LWLWLWLWW": [0.04, 0.08, 0.08, 0.08, 0.08, 0.08, 0.08, 0.02, 0.26],
            "LWLWLWLWLL": [0.04, 0.08, 0.08, 0.08, 0.08, 0.08, 0.08, 0.02, 0.26, 0.02],
            "LWLWLWLWLWW": [0.04, 0.08, 0.08, 0.08, 0.08, 0.08, 0.08, 0.02, 0.26, 0.02, 0.16],
            "LWLWLWLWLWLW": [0.04, 0.08, 0.08, 0.08, 0.08, 0.08, 0.08, 0.02, 0.26, 0.02, 0.16, 0.16],
            "LWLWLWLWLWLL": [0.04, 0.08, 0.08, 0.08, 0.08, 0.08, 0.08, 0.02, 0.26, 0.02, 0.16, 0.16],
            "WW": [0.04, 0.08],
            "WLL": [0.04, 0.08, 0.08],
            "WLWW": [0.04, 0.08, 0.08, 0.08],
            "WLWLL": [0.04, 0.08, 0.08, 0.08, 0.08],
            "WLWLWW": [0.04, 0.08, 0.08, 0.08, 0.08, 0.20],
            "WLWLWLW": [0.04, 0.08, 0.08, 0.08, 0.08, 0.20, 0.20],
            "WLWLWLL": [0.04, 0.08, 0.08, 0.08, 0.08, 0.20, 0.20]
        }
        self.sequence_serial = {seq: idx + 1 for idx, seq in enumerate(self.sequence_map.keys())}

    def _get_next_lot(self, history: str):
        history = history.upper().strip()
        possible_paths = [seq for seq in self.sequence_map.keys() if seq.startswith(history)]
        if not possible_paths: return None
        reference_path = self.sequence_map[possible_paths[0]]
        if len(history) < len(reference_path): return reference_path[len(history)]
        return None

    def calculate_optimal_hedge(self, state: TradeState) -> Dict[str, Any]:
        raw_target_lot = self._get_next_lot(state.eval_sequence)
        if raw_target_lot is None:
            return {"recommended_lot": state.base_broker_lot, "exhausted": True}
            
        final_target_lot = state.base_broker_lot if state.eval_sequence == "" else (raw_target_lot * state.scale_factor)
        return {"recommended_lot": final_target_lot, "exhausted": False}

# ==========================================
# 3. SQLITE DATABASE
# ==========================================
class DatabaseManager:
    def __init__(self, db_name="hedge_trades.db"):
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self.create_tables()

    def create_tables(self):
        query = """
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sequence TEXT, eval_balance REAL, broker_balance REAL, lot_used REAL, result TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
        self.conn.execute(query)
        self.conn.commit()

    def insert_trade(self, record):
        query = "INSERT INTO trades (sequence, eval_balance, broker_balance, lot_used, result) VALUES (?, ?, ?, ?, ?)"
        self.conn.execute(query, (record.get("sequence", ""), record["eval_balance"], record["broker_balance"], record["recommended_lot"], record["result"]))
        self.conn.commit()

    def get_all_trades(self):
        return self.conn.execute("SELECT id, sequence, eval_balance, broker_balance, lot_used, result, timestamp FROM trades ORDER BY id ASC").fetchall()

    def reset_database(self):
        self.conn.execute("DELETE FROM trades")
        self.conn.execute("DELETE FROM sqlite_sequence WHERE name='trades'")
        self.conn.commit()

# ==========================================
# 4. SESSION STATE INITIALIZATION
# ==========================================
def init_session_state():
    if 'db' not in st.session_state:
        st.session_state.db = DatabaseManager()
        st.session_state.optimizer = SequenceOptimizer()
        
        # UI Input defaults
        st.session_state.inp_eval_target = 53000.0
        st.session_state.inp_eval_dd = 48000.0
        st.session_state.inp_dd_trigger = 52000.0
        st.session_state.inp_dd_lock = 50100.0
        st.session_state.inp_futures_lot = 10.0
        st.session_state.inp_sl_points = 10.0
        st.session_state.inp_tp_points = 15.0
        st.session_state.inp_broker_bal = 1500.0
        st.session_state.inp_base_broker_lot = 0.04
        
        # Live System logic variables
        st.session_state.current_sequence = ""
        st.session_state.trade_counter = 1
        st.session_state.current_recommended_lot = 0.04
        st.session_state.live_eval_balance = 50000.0
        st.session_state.live_broker_balance = 1500.0
        st.session_state.live_dd_limit = 48000.0
        st.session_state.initial_broker_bal = 1500.0
        st.session_state.dynamic_dd_locked = False
        st.session_state.live_scale_factor = 1.0
        st.session_state.is_exhausted = False
        st.session_state.status_message = ""
        
        restore_session()

def restore_session():
    trades = st.session_state.db.get_all_trades()
    if trades:
        first_trade = trades[0]
        try:
            first_lot = float(first_trade[4])
            st.session_state.live_scale_factor = 0.5 if first_lot <= 0.03 else 1.0
        except: pass
        
        last_trade = trades[-1]
        st.session_state.current_sequence = last_trade[1]
        st.session_state.live_eval_balance = float(last_trade[2])
        st.session_state.live_broker_balance = float(last_trade[3])
        st.session_state.trade_counter = len(trades) + 1
        
        try:
            first_broker_after = float(first_trade[3])
            tp = st.session_state.inp_tp_points
            sl = st.session_state.inp_sl_points
            st.session_state.initial_broker_bal = first_broker_after + (first_lot * tp * 100.0) if first_trade[5] == "EVAL WIN" else first_broker_after - (first_lot * sl * 100.0)
        except:
            st.session_state.initial_broker_bal = 750.0 if st.session_state.live_scale_factor == 0.5 else 1500.0

init_session_state()

# ==========================================
# 5. LOGIC CALLBACKS
# ==========================================
def apply_25k_50k_template():
    if st.session_state.ui_eval_bal == "25000":
        st.session_state.inp_eval_target = 26500.0
        st.session_state.inp_eval_dd = 24000.0
        st.session_state.inp_dd_trigger = 26000.0
        st.session_state.inp_dd_lock = 25050.0
        st.session_state.inp_futures_lot = 5.0
        st.session_state.inp_broker_bal = 750.0
        st.session_state.inp_base_broker_lot = 0.02
    else:
        st.session_state.inp_eval_target = 53000.0
        st.session_state.inp_eval_dd = 48000.0
        st.session_state.inp_dd_trigger = 52000.0
        st.session_state.inp_dd_lock = 50100.0
        st.session_state.inp_futures_lot = 10.0
        st.session_state.inp_broker_bal = 1500.0
        st.session_state.inp_base_broker_lot = 0.04

def process_trade(result_str, seq_char):
    eval_lot = st.session_state.inp_futures_lot
    broker_lot = st.session_state.current_recommended_lot
    sl_pts = st.session_state.inp_sl_points
    tp_pts = st.session_state.inp_tp_points
    
    if result_str == "EVAL WIN":
        new_eval = st.session_state.live_eval_balance + (eval_lot * tp_pts * 10.0)
        new_broker = st.session_state.live_broker_balance - (broker_lot * tp_pts * 100.0)
    else:
        new_eval = st.session_state.live_eval_balance - (eval_lot * sl_pts * 10.0)
        new_broker = st.session_state.live_broker_balance + (broker_lot * sl_pts * 100.0)

    st.session_state.live_broker_balance = max(0.0, round(new_broker, 2))
    st.session_state.live_eval_balance = round(new_eval, 2)
    st.session_state.current_sequence += seq_char

    record = {
        "sequence": st.session_state.current_sequence,
        "eval_balance": st.session_state.live_eval_balance,  
        "broker_balance": st.session_state.live_broker_balance,
        "recommended_lot": broker_lot,
        "result": result_str
    }
    st.session_state.db.insert_trade(record)
    st.session_state.trade_counter += 1

def reset_system():
    st.session_state.db.reset_database()
    st.session_state.trade_counter = 1
    st.session_state.current_sequence = ""
    st.session_state.live_scale_factor = float(st.session_state.ui_eval_bal) / 50000.0
    st.session_state.live_eval_balance = float(st.session_state.ui_eval_bal)
    st.session_state.live_broker_balance = st.session_state.inp_broker_bal
    st.session_state.live_dd_limit = st.session_state.inp_eval_dd
    st.session_state.initial_broker_bal = st.session_state.live_broker_balance
    st.session_state.dynamic_dd_locked = False
    st.session_state.is_exhausted = False
    st.session_state.status_message = ""

def apply_settings():
    st.session_state.live_scale_factor = float(st.session_state.ui_eval_bal) / 50000.0
    if st.session_state.trade_counter == 1:
        st.session_state.live_eval_balance = float(st.session_state.ui_eval_bal)
        st.session_state.live_broker_balance = st.session_state.inp_broker_bal
        st.session_state.initial_broker_bal = st.session_state.live_broker_balance
        st.session_state.live_dd_limit = st.session_state.inp_eval_dd
        st.session_state.dynamic_dd_locked = False
    st.session_state.status_message = "Settings Applied successfully."

# ==========================================
# 6. ENGINE EXECUTION BEFORE RENDER
# ==========================================
state = TradeState(
    eval_balance=st.session_state.live_eval_balance,
    eval_target=st.session_state.inp_eval_target,
    eval_dd_limit=st.session_state.live_dd_limit,
    broker_balance=st.session_state.live_broker_balance,
    futures_lot=st.session_state.inp_futures_lot,
    sl_points=st.session_state.inp_sl_points,
    tp_points=st.session_state.inp_tp_points,
    eval_sequence=st.session_state.current_sequence,
    base_broker_lot=st.session_state.inp_base_broker_lot,
    trade_number=st.session_state.trade_counter,
    scale_factor=st.session_state.live_scale_factor
)

calc = st.session_state.optimizer.calculate_optimal_hedge(state)
st.session_state.is_exhausted = calc["exhausted"]
st.session_state.current_recommended_lot = calc["recommended_lot"]
rec_lot = calc["recommended_lot"]  # Local variable to securely pass to the UI string

# Dynamic Drawdown Check
if st.session_state.get('ui_dd_type', 'Dynamic') == "Dynamic" and not st.session_state.dynamic_dd_locked:
    if state.eval_balance >= st.session_state.inp_dd_trigger:
        st.session_state.live_dd_limit = st.session_state.inp_dd_lock
        st.session_state.dynamic_dd_locked = True
        st.session_state.status_message = f"DRAWDOWN LOCKED! Eval reached ${st.session_state.inp_dd_trigger:,.2f}. Limit secured at ${st.session_state.inp_dd_lock:,.2f}."

# Check Win / Loss / End Condition
term_state = None
if state.eval_balance >= state.eval_target:
    term_state = "PASS"
    st.session_state.status_message = "SUCCESS: EVALUATION PASSED!"
elif state.eval_balance <= state.eval_dd_limit:
    term_state = "FAIL"
    st.session_state.status_message = "HEDGE SECURED: MAX DRAWDOWN REACHED."
elif st.session_state.is_exhausted and state.eval_sequence != "":
    term_state = "END"
    pnl = state.broker_balance - st.session_state.initial_broker_bal
    st.session_state.status_message = "SEQUENCE EXHAUSTED (Broker Profit Secured)" if pnl > 0 else "SEQUENCE EXHAUSTED (No Limits Met)"

# ==========================================
# 7. UI RENDER - TABS
# ==========================================
tab1, tab2 = st.tabs(["📊 Execution Dashboard", "⚙️ Settings & Inputs"])

with tab2:
    st.header("Settings & Inputs")
    colA, colB = st.columns(2)
    with colA:
        st.subheader("Evaluation Account")
        st.selectbox("Drawdown Tracking", ["Dynamic", "Static"], key="ui_dd_type")
        st.selectbox("Starting Eval Balance", ["50000", "25000"], key="ui_eval_bal", on_change=apply_25k_50k_template)
        st.number_input("Profit Target", value=st.session_state.inp_eval_target, key="inp_eval_target")
        st.number_input("Active Drawdown Limit", value=st.session_state.inp_eval_dd, key="inp_eval_dd")
        st.number_input("DD Trigger Balance", value=st.session_state.inp_dd_trigger, key="inp_dd_trigger")
        st.number_input("DD Lock Balance", value=st.session_state.inp_dd_lock, key="inp_dd_lock")
        st.number_input("Futures Lot Size", value=st.session_state.inp_futures_lot, key="inp_futures_lot")
        st.number_input("Stop Loss (Points)", value=st.session_state.inp_sl_points, key="inp_sl_points")
        st.number_input("Take Profit (Points)", value=st.session_state.inp_tp_points, key="inp_tp_points")
    with colB:
        st.subheader("Broker Account")
        st.number_input("Broker Balance", value=st.session_state.inp_broker_bal, key="inp_broker_bal")
        st.number_input("Base Broker Lot", value=st.session_state.inp_base_broker_lot, key="inp_base_broker_lot")
        
    st.button("Apply Settings & Refresh System", on_click=apply_settings, type="primary")

with tab1:
    if st.session_state.status_message:
        if "SUCCESS" in st.session_state.status_message or "DRAWDOWN" in st.session_state.status_message:
            st.success(st.session_state.status_message)
        else:
            st.warning(st.session_state.status_message)

    col1, col2, col3 = st.columns([2, 2.5, 2])
    
    # --- LEFT PANEL: Projections (Wrapped correctly to fix clipping and text color) ---
    pnl = state.broker_balance - st.session_state.initial_broker_bal
    pnl_color = "#00E676" if pnl > 0 else "#FF5252" if pnl < 0 else "#AAAAAA"
    pnl_text = f"+${pnl:.2f}" if pnl > 0 else f"-${abs(pnl):.2f}" if pnl < 0 else "$0.00"
    
    left_html = f"""
    <div style="background-color: #1A1A1A; border-radius: 8px; border: 1px solid #333333; padding: 25px; height: 100%; color: #FFFFFF;">
        <div style="text-align: center; font-weight: bold; font-size: 18px; margin-bottom: 20px;">ACCOUNT OVERVIEW</div>
        
        <div style="font-size:16px; line-height:1.8; margin-bottom: 30px;">
            Eval Balance: <span style='color:#00E676; font-weight:bold;'>${state.eval_balance:,.2f}</span><br>
            Broker Balance: <span style='color:#FFFFFF; font-weight:bold;'>${state.broker_balance:,.2f}</span><br>
            Total Broker PnL: <span style='color:{pnl_color}; font-weight:bold;'>{pnl_text}</span>
        </div>
        
        <div style="text-align: center; font-weight: bold; font-size: 18px; margin-bottom: 15px;">PREDICTED OUTCOMES (NEXT TRADE)</div>
    """
    
    if term_state:
        left_html += f"<div style='background-color: #222; padding: 20px; border-radius: 8px; text-align: center;'><b style='color:#FF8C00; font-size: 16px;'>SEQUENCE TERMINATED: {term_state}</b></div>"
    else:
        ewin_amt = state.futures_lot * state.tp_points * 10.0
        bloss_amt = rec_lot * state.tp_points * 100.0
        eloss_amt = state.futures_lot * state.sl_points * 10.0
        bwin_amt = rec_lot * state.sl_points * 100.0
        
        pnl_W = (state.broker_balance - bloss_amt) - st.session_state.initial_broker_bal
        pnl_W_str = f"+${pnl_W:,.2f}" if pnl_W > 0 else f"-${abs(pnl_W):,.2f}"
        c_W = '#00E676' if pnl_W > 0 else '#FF5252'
        
        pnl_L = (state.broker_balance + bwin_amt) - st.session_state.initial_broker_bal
        pnl_L_str = f"+${pnl_L:,.2f}" if pnl_L > 0 else f"-${abs(pnl_L):,.2f}"
        c_L = '#00E676' if pnl_L > 0 else '#FF5252'

        left_html += f"""
        <div style='background-color: #222; padding: 20px; border-radius: 8px; line-height: 1.8; font-size: 15px; color: #FFFFFF;'>
            <b style='color:#00E676; font-size: 16px;'>IF EVAL WINS (W):</b><br>
            Eval PnL: <span style='color:#00E676;'>+${ewin_amt:,.2f}</span> | Broker PnL: <span style='color:#FF5252;'>-${bloss_amt:,.2f}</span><br>
            New Eval: <span style='color:#00E676;'>${state.eval_balance + ewin_amt:,.2f}</span><br>
            New Total Broker PnL: <span style='color:{c_W}; font-weight:bold;'>{pnl_W_str}</span><br><br>
            
            <b style='color:#FF5252; font-size: 16px;'>IF EVAL LOSES (L):</b><br>
            Eval PnL: <span style='color:#FF5252;'>-${eloss_amt:,.2f}</span> | Broker PnL: <span style='color:#00E676;'>+${bwin_amt:,.2f}</span><br>
            New Eval: <span style='color:#FF5252;'>${state.eval_balance - eloss_amt:,.2f}</span><br>
            New Total Broker PnL: <span style='color:{c_L}; font-weight:bold;'>{pnl_L_str}</span>
        </div>
        """
    left_html += "</div>"
    
    with col1:
        st.markdown(left_html, unsafe_allow_html=True)

    # --- CENTER PANEL: Action Buttons ---
    lot_txt = term_state if term_state else f"{rec_lot:.2f}"
    center_html = f"""
    <div style="background-color: #1A1A1A; border-radius: 8px; border: 1px solid #333333; padding: 40px 20px; color: #FFFFFF; text-align: center;">
        <div style="font-size:22px; font-weight: bold; margin-bottom: 20px;">NEXT BROKER LOT TO EXECUTE</div>
        <div style="font-size: 110px; font-weight: 900; color: #00E676; line-height: 1;">{lot_txt}</div>
    </div>
    """
    
    with col2:
        st.markdown(center_html, unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        
        ca, cb = st.columns(2)
        with ca: st.button("EVAL WINS (W)", use_container_width=True, on_click=process_trade, args=("EVAL WIN", "W"), disabled=bool(term_state))
        with cb: st.button("EVAL LOSES (L)", use_container_width=True, on_click=process_trade, args=("EVAL LOSS", "L"), disabled=bool(term_state))
        
        st.markdown("<br>", unsafe_allow_html=True)
        st.button("RESET ALL DATA", use_container_width=True, on_click=reset_system)

    # --- RIGHT PANEL: Sequences (Wrapped correctly) ---
    right_html = f"""
    <div style="background-color: #1A1A1A; border-radius: 8px; border: 1px solid #333333; padding: 25px; height: 100%; color: #FFFFFF;">
        <div style="text-align: center; font-weight: bold; font-size: 18px; margin-bottom: 20px;">ACTIVE SEQUENCE PATHS</div>
        <div style="background-color:#111; padding:20px; border-radius:8px; font-family:monospace; line-height:1.8; font-size:15px; color: #FFFFFF;">
    """
    possible_paths = [seq for seq in st.session_state.optimizer.sequence_map.keys() if seq.startswith(state.eval_sequence)]
    if not possible_paths:
        right_html += "<span style='color:#FF5252; font-weight:bold;'>Path Unknown or Ended.</span>"
    else:
        red_seqs, blue_seqs, yel_seqs = {"LWLL", "LWLWLL", "LWLWLWLL", "WLWLL"}, {"LWWW", "LWLWWW", "LWLWLWLWW"}, {"LWWW", "LWWLWW", "LWLWWW", "LWLWLWLWLWW", "WLWLWW"}
        colored_hist = "".join(["<span style='color:#00E676; font-weight:bold;'>W</span>" if c == 'W' else "<span style='color:#FF5252; font-weight:bold;'>L</span>" for c in state.eval_sequence])
        
        for seq in possible_paths:
            serial_str = f"<span style='color:#777777;'>{st.session_state.optimizer.sequence_serial[seq]:02d}. </span>"
            rem = seq[len(state.eval_sequence):]
            
            raw_lots = list(st.session_state.optimizer.sequence_map[seq])
            scaled_lots = [lot * state.scale_factor for lot in raw_lots]
            if scaled_lots: scaled_lots[0] = state.base_broker_lot
            
            fmt_lots = []
            for i, lot in enumerate(scaled_lots):
                if seq in yel_seqs and i == len(scaled_lots) - 1:
                    fmt_lots.append(f"<span style='color:#FFFF00; font-size:18px; font-weight:900;'>[{lot:.2f}]</span>")
                else:
                    fmt_lots.append(f"{lot:.2f}")
                    
            inner = ", ".join(fmt_lots)
            clr = "#FF5252" if seq in red_seqs else "#42A5F5" if seq in blue_seqs else "#777777"
            html_lots = f"<span style='color:{clr}; font-weight:bold;'> [{inner}]</span>"
            
            right_html += f"<div>{serial_str}{colored_hist}<span style='color:#777;'>{rem}</span>{html_lots}</div>"
            
    right_html += "</div></div>"
    
    with col3:
        st.markdown(right_html, unsafe_allow_html=True)

    # --- BOTTOM PANEL: Table Log ---
    st.markdown("<br><b style='color:#AAAAAA; font-size:18px;'>CURRENT TRADE LOG</b>", unsafe_allow_html=True)
    trades = st.session_state.db.get_all_trades()
    if trades:
        df = pd.DataFrame(trades, columns=["Trade #", "Sequence Path", "Eval Balance", "Broker Balance", "Broker Lot", "Eval Result", "Timestamp"])
        df["Eval Balance"] = df["Eval Balance"].apply(lambda x: f"${x:,.2f}")
        df["Broker Balance"] = df["Broker Balance"].apply(lambda x: f"${x:,.2f}")
        st.dataframe(df, use_container_width=True, hide_index=True)
    else:
        st.info("No trades logged yet. Click W or L to begin.")
