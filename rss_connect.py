import xlwings as xw
import time
import csv
import os
import shutil
from datetime import datetime
from pynput import keyboard  # キーボード監視用

# --- ログ記録用関数 ---
def write_csv(filename, data, header=None):
    file_exists = os.path.isfile(filename)
    # Excelで文字化けしないよう utf-8-sig で保存
    with open(filename, 'a', newline='', encoding='utf-8-sig') as f:
        writer = csv.writer(f)
        if not file_exists and header:
            writer.writerow(['記録日時'] + header)
        writer.writerow([datetime.now().strftime("%H:%M:%S")] + data)

# --- トレンド判定用波形分析アルゴリズム ---
def get_swing_points(highs, lows):
    peaks = []
    valleys = []
    # データは上が古く、下が新しい(昇順)と想定
    for i in range(1, len(highs) - 1):
        # 山の判定: 前の足から上がって(または維持)、次の足で下がった箇所
        if highs[i] >= highs[i-1] and highs[i] > highs[i+1]:
            peaks.append(highs[i])
        # 谷の判定: 前の足から下がって(または維持)、次の足で上がった箇所
        if lows[i] <= lows[i-1] and lows[i] < lows[i+1]:
            valleys.append(lows[i])
    return peaks, valleys

def analyze_trend_from_data(highs, lows):
    # 高値と安値のペアが両方とも正常な数値である場合のみ抽出（片方だけ空データならその足ごと除外）
    clean_h = []
    clean_l = []
    for h, l in zip(highs, lows):
        if isinstance(h, (int, float)) and isinstance(l, (int, float)):
            clean_h.append(float(h))
            clean_l.append(float(l))
    
    if len(clean_h) < 3 or len(clean_l) < 3:
        return 'NONE', 'データ不足(空データが多い等)'
        
    peaks, valleys = get_swing_points(clean_h, clean_l)
    
    # 少なくとも山と谷が2つずつ検出できているか確認
    if len(peaks) >= 2 and len(valleys) >= 2:
        recent_peak = peaks[-1]
        prev_peak = peaks[-2]
        recent_valley = valleys[-1]
        prev_valley = valleys[-2]
        
        # 同値（=）の場合は維持（継続）とみなすための文字列
        if recent_peak > prev_peak:
            peak_str = f"高値({recent_peak} > {prev_peak})"
        elif recent_peak == prev_peak:
            peak_str = f"高値({recent_peak} = {prev_peak})"
        else:
            peak_str = f"高値({recent_peak} < {prev_peak})"
            
        if recent_valley > prev_valley:
            valley_str = f"安値({recent_valley} > {prev_valley})"
        elif recent_valley == prev_valley:
            valley_str = f"安値({recent_valley} = {prev_valley})"
        else:
            valley_str = f"安値({recent_valley} < {prev_valley})"
        
        # ダウ理論の判定（高値切り上げ/維持 ＋ 安値切り上げ/維持）※完全に同じ波形の場合は除く
        is_up = (recent_peak >= prev_peak) and (recent_valley >= prev_valley)
        is_down = (recent_peak <= prev_peak) and (recent_valley <= prev_valley)
        is_flat = (recent_peak == prev_peak) and (recent_valley == prev_valley)
        
        if is_up and not is_flat:
            return 'LONG', f"{peak_str} / {valley_str}", recent_peak
        elif is_down and not is_flat:
            return 'SHORT', f"{peak_str} / {valley_str}", recent_peak
        else:
            return 'NONE', f"チグハグ({peak_str} / {valley_str})", recent_peak
            
    return 'NONE', f"波形検出不足 (山:{len(peaks)}個, 谷:{len(valleys)}個)", None

def check_trend_direction(wb, silent=False):
    try:
        sheet = wb.sheets["ChartData"]
        
        # 100行分のデータを取得
        # ユーザー設定: 週足・日足・60分足・15分足・5分足の順
        # 週足(A1起点) -> 高値D列、安値E列
        w_data = sheet.range("D3:E102").value or []
        # 日足(H1起点) -> 高値K列、安値L列
        d_data = sheet.range("K3:L102").value or []
        # 60分足(O1起点) -> 高値R列、安値S列
        m60_data = sheet.range("R3:S102").value or []
        # 15分足(V1起点想定) -> 高値Y列、安値Z列
        m15_data = sheet.range("Y3:Z102").value or []
        # 5分足(AC1起点) -> 高値AF列、安値AG列
        m5_data = sheet.range("AF3:AG102").value or []
        
        # 取得した2次元配列 [[High, Low], ...] からそれぞれ抽出
        # 元データが「降順(最新が一番上)」とのことなので、Python側で「昇順(古い順)」に反転させます [::-1]
        w_h = [row[0] for row in w_data if row is not None and len(row) > 0][::-1]
        w_l = [row[1] for row in w_data if row is not None and len(row) > 1][::-1]
        
        d_h = [row[0] for row in d_data if row is not None and len(row) > 0][::-1]
        d_l = [row[1] for row in d_data if row is not None and len(row) > 1][::-1]
        
        m60_h = [row[0] for row in m60_data if row is not None and len(row) > 0][::-1]
        m60_l = [row[1] for row in m60_data if row is not None and len(row) > 1][::-1]
        
        m15_h = [row[0] for row in m15_data if row is not None and len(row) > 0][::-1]
        m15_l = [row[1] for row in m15_data if row is not None and len(row) > 1][::-1]
        
        m5_h = [row[0] for row in m5_data if row is not None and len(row) > 0][::-1]
        m5_l = [row[1] for row in m5_data if row is not None and len(row) > 1][::-1]
        
        w_trend, w_det, _ = analyze_trend_from_data(w_h, w_l)
        d_trend, d_det, _ = analyze_trend_from_data(d_h, d_l)
        m60_trend, m60_det, _ = analyze_trend_from_data(m60_h, m60_l)
        m15_trend, m15_det, _ = analyze_trend_from_data(m15_h, m15_l)
        m5_trend, m5_det, prev_peak_5m = analyze_trend_from_data(m5_h, m5_l)
        
        if not silent:
            print("\n=== 波形分析によるトレンド詳細判定 ===")
            print(f" [週足]   {w_trend:<5} : {w_det} (※環境認識)")
            print(f" [日足]   {d_trend:<5} : {d_det} (※環境認識)")
            print(f" [60分足] {m60_trend:<5} : {m60_det} (※参考:将来の自動エントリー用)")
            print(f" [15分足] {m15_trend:<5} : {m15_det} (※参考:将来の自動エントリー用)")
            print(f" [5分足]  {m5_trend:<5} : {m5_det}  (※参考:将来の自動エントリー用)")
            print("======================================")
        
        # エントリー許可は「週足と日足」の大局的なトレンドのみで判断
        if w_trend == 'LONG' and d_trend == 'LONG':
            return 'LONG', prev_peak_5m
        elif w_trend == 'SHORT' and d_trend == 'SHORT':
            return 'SHORT', prev_peak_5m
        else:
            return 'NONE', prev_peak_5m
    except Exception as e:
        if not silent:
            import traceback
            print(f"\n!!! トレンドデータの取得に失敗しました (ChartDataシートの設定を確認してください): {e}")
            print("▼詳細なエラー原因:")
            traceback.print_exc()
        return 'NONE', None

# --- グローバル変数 ---
trigger_action = None  # 'BUY', 'SELL', 'STOP' を管理

def on_press(key):
    global trigger_action
    try:
        if key == keyboard.Key.up:
            trigger_action = 'BUY'        # ↑キーで買い
        elif key == keyboard.Key.down:
            trigger_action = 'SELL'       # ↓キーで売り
        elif key == keyboard.Key.right:
            trigger_action = 'CLOSE_ALL'  # →キーで強制決済
        elif key == keyboard.Key.esc:
            trigger_action = 'STOP'       # Escキーで安全終了
    except AttributeError:
        pass

def main():
    global trigger_action
    
    # --- 設定エリア ---
    TARGET_SHEET = "Sheet1"
    ENTRY_LOTS = 11  # 11枚固定
    
    # 状態管理
    is_position = False
    is_ordering = False       # 指値注文中フラグ
    order_price = 0           # 指値価格
    queue_volume = 0          # 待ち行列（自分の前の注文数）
    target_lots = 0           # 発注目標枚数
    filled_lots = 0           # 約定済枚数
    
    pos_type = None  # 'LONG' or 'SHORT'
    entry_price = 0
    remaining_lots = 0
    last_total_volume = 0
    last_price = 0
    step1_done = step2_done = step3_done = False

    # --- 起動時の初期化処理 ---
    # market_history.csv が残っていたら削除してリセット
    if os.path.exists("market_history.csv"):
        try:
            os.remove("market_history.csv")
            print(">>> 前回のマーケットヒストリーをリセットしました。")
        except PermissionError:
            print("!!! エラー: market_history.csv がExcel等で開かれています。閉じてから再起動してください。")
            return

    # キーボードリスナーの開始
    listener = keyboard.Listener(on_press=on_press)
    listener.start()

    try:
        wb = xw.books.active
        sheet = wb.sheets[TARGET_SHEET]
        
        # トレンドの事前判定
        allowed_direction, prev_peak_5m = check_trend_direction(wb)
        direction_str = "【買い(LONG)のみ許可】" if allowed_direction == 'LONG' else "【売り(SHORT)のみ許可】" if allowed_direction == 'SHORT' else "【見送り(条件不一致)】"
        
        m_header = ["方向", "現在値", "約定枚数", "歩み1", "歩み2", "歩み3", "歩み4", "累計出来高", "買気配数量", "売気配数量", "買気配値", "売気配値", "詳細時刻"]
        t_header = ["イベント", "売買区分", "価格", "枚数", "残枚数", "損益幅"]

        print("--- システム稼働中 ---")
        print(f" 本日のトレンド判定: {direction_str}")
        print(" [↑]:買い  [↓]:売り  [→]:強制決済  [Esc]:保存して終了 ")
        
        # 初回データ取得
        last_total_volume = sheet.range("D1").value
        last_price = sheet.range("A1").value

        loop_counter = 0

        while True:
            if trigger_action == 'STOP': break

            # 5秒に1回 (loop_counter % 10 == 0 if sleep 0.5) 下位足リロード
            if loop_counter % 10 == 0:
                allowed_direction, prev_peak_5m = check_trend_direction(wb, silent=True)
            loop_counter += 1

            # Excelから一括読み取り (A1:H4) - 気配値や気配数量2〜4を含む
            data_matrix = sheet.range("A1:H4").value
            curr_p = data_matrix[0][0]     # A1: 現在値
            walks = [data_matrix[i][1] for i in range(4)] # B1-B4: 歩み
            total_v = data_matrix[0][3]    # D1: 累計出来高
            update_t = data_matrix[0][4]   # E1: 詳細時刻
            buy_queue = data_matrix[0][5]  # F1: 最良買気配数量1
            sell_queue = data_matrix[0][6] # G1: 最良売気配数量1
            best_bid_p = data_matrix[0][7] # H1: 買気配値1
            best_ask_p = data_matrix[1][7] # H2: 売気配値1

            # 1. 出来高変化時のログ記録 (高密度モード)
            new_trades = total_v - last_total_volume if last_total_volume > 0 else 0
            
            if new_trades > 0:
                # 矢印判定
                if curr_p > last_price: direction = "↑"
                elif curr_p < last_price: direction = "↓"
                else: direction = "→"

                # 履歴保存
                market_data = [direction, curr_p, new_trades] + walks + [total_v, buy_queue, sell_queue, best_bid_p, best_ask_p, update_t]
                write_csv("market_history.csv", market_data, m_header)
                
                last_total_volume = total_v
                last_price = curr_p
                
                # --- 約定シミュレーション (注文中の場合) ---
                if is_ordering:
                    if pos_type == 'LONG':
                        # 現在値が指値と同じなら、歩み値（出来高）分だけ待ち行列を減らす
                        if curr_p == order_price:
                            queue_volume -= new_trades
                            if queue_volume < 0:
                                new_fills = min(abs(queue_volume), target_lots - filled_lots)
                                if new_fills > 0:
                                    filled_lots += new_fills
                                    queue_volume = 0 # ゼロリセット
                                    print(f"\n[{update_t}] 指値一部約定: {new_fills}枚 (計: {filled_lots}/{target_lots}枚)")
                                    
                                if filled_lots >= target_lots:
                                    is_ordering = False
                                    is_position = True
                                    entry_price = order_price
                                    remaining_lots = filled_lots
                                    step1_done = step2_done = step3_done = False
                                    write_csv("trade_log.csv", [f"★{pos_type}全量約定", pos_type, entry_price, filled_lots, remaining_lots, 0], t_header)
                                    print(f"\n[{update_t}] {pos_type}全量約定完了: {entry_price}円 ({filled_lots}枚)")
                        
                        # 現在値が指値より下（突き抜けた）なら即時全量約定
                        elif curr_p < order_price:
                            filled_lots = target_lots
                            is_ordering = False
                            is_position = True
                            entry_price = order_price
                            remaining_lots = filled_lots
                            step1_done = step2_done = step3_done = False
                            write_csv("trade_log.csv", [f"★{pos_type}突き抜け約定", pos_type, entry_price, filled_lots, remaining_lots, 0], t_header)
                            print(f"\n[{update_t}] {pos_type}突き抜け約定: {entry_price}円 ({filled_lots}枚)")
                        
                        # 現在値が指値+20円以上になったらキャンセル（置き去り）
                        elif curr_p >= order_price + 20:
                            is_ordering = False
                            if filled_lots > 0:
                                is_position = True
                                entry_price = order_price
                                remaining_lots = filled_lots
                                step1_done = step2_done = step3_done = False
                                write_csv("trade_log.csv", [f"★{pos_type}一部約定後取消", pos_type, entry_price, filled_lots, remaining_lots, 0], t_header)
                                print(f"\n[{update_t}] 板移動(20円離脱)のため未約定分をキャンセル。一部約定({filled_lots}枚)で進行します。")
                            else:
                                write_csv("trade_log.csv", [f"★{pos_type}注文取消", pos_type, order_price, 0, 0, 0], t_header)
                                print(f"\n[{update_t}] 板移動のため指値注文を全量キャンセルしました。")

            # --- 自動エントリー判定 (LONGのみ) ---
            if not is_position and not is_ordering and allowed_direction == 'LONG' and prev_peak_5m is not None:
                if curr_p > prev_peak_5m:
                    is_ordering = True
                    pos_type = 'LONG'
                    order_price = prev_peak_5m
                    queue_volume = buy_queue if buy_queue else 0
                    target_lots = ENTRY_LOTS
                    filled_lots = 0
                    print(f"\n[{update_t}] 【自動】5分足高値({prev_peak_5m}円)ブレイク！")
                    print(f"[{update_t}] 指値注文を発注: {order_price}円 (待ち行列:{queue_volume}枚)")
                    write_csv("trade_log.csv", [f"★指値発注({pos_type})", pos_type, order_price, target_lots, 0, 0], t_header)

            # 2. キー入力による任意エントリー判定 (デバッグ/手動用)
            if not is_position and not is_ordering and trigger_action in ['BUY', 'SELL']:
                pos_type = 'LONG' if trigger_action == 'BUY' else 'SHORT'
                
                # トレンド判定によるフィルター
                if pos_type != allowed_direction:
                    print(f"\n[{update_t}] ブロックされました: 本日は {direction_str} のため {pos_type} は無効です。")
                    trigger_action = None
                    continue

                is_position = True
                entry_price = curr_p
                remaining_lots = ENTRY_LOTS
                step1_done = step2_done = step3_done = False
                
                write_csv("trade_log.csv", [f"★{pos_type}開始(手動)", pos_type, entry_price, ENTRY_LOTS, remaining_lots, 0], t_header)
                print(f"\n[{update_t}] {pos_type}エントリー開始: {entry_price}円")
                trigger_action = None

            # 3. 決済ロジック (保有時のみ稼働)
            if is_position:
                # 損益幅計算（売りは逆転）
                diff = (curr_p - entry_price) if pos_type == 'LONG' else (entry_price - curr_p)
                
                # 手動での強制決済 (→キー)
                if trigger_action == 'CLOSE_ALL':
                    write_csv("trade_log.csv", ["!!!強制決済", pos_type, curr_p, remaining_lots, 0, diff], t_header)
                    print(f"\n[{update_t}] 手動で強制決済を執行しました: {curr_p}円 (損益: {diff}円)")
                    is_position = False
                    trigger_action = None
                
                # 損切り (30円逆行)
                elif diff <= -30:
                    write_csv("trade_log.csv", ["!!!損切り", pos_type, curr_p, remaining_lots, 0, diff], t_header)
                    print(f"\n[{update_t}] 損切り執行: {curr_p}円")
                    is_position = False
                
                # 分割利確 (30/50/100円) - 残枚数に応じて可変
                elif diff >= 30 and not step1_done:
                    close_qty = min(remaining_lots, 5)
                    if close_qty > 0:
                        remaining_lots -= close_qty
                        write_csv("trade_log.csv", ["利確1(30円)", pos_type, curr_p, close_qty, remaining_lots, diff], t_header)
                        print(f"\n[{update_t}] 利確1達成: {curr_p}円 (残り:{remaining_lots}枚)")
                    step1_done = True
                
                elif diff >= 50 and not step2_done:
                    close_qty = min(remaining_lots, 2)
                    if close_qty > 0:
                        remaining_lots -= close_qty
                        write_csv("trade_log.csv", ["利確2(50円)", pos_type, curr_p, close_qty, remaining_lots, diff], t_header)
                        print(f"\n[{update_t}] 利確2達成: {curr_p}円 (残り:{remaining_lots}枚)")
                    step2_done = True

                elif diff >= 100 and not step3_done:
                    close_qty = min(remaining_lots, 2)
                    if close_qty > 0:
                        remaining_lots -= close_qty
                        write_csv("trade_log.csv", ["利確3(100円)", pos_type, curr_p, close_qty, remaining_lots, diff], t_header)
                        print(f"\n[{update_t}] 利確3達成: {curr_p}円 (残り:{remaining_lots}枚)")
                    step3_done = True

                # 最終決済：残り保有ありかつ建値+5円まで戻った時
                elif step1_done and diff <= 5 and remaining_lots > 0:
                    write_csv("trade_log.csv", ["最終決済(建値)", pos_type, curr_p, remaining_lots, 0, diff], t_header)
                    print(f"\n[{update_t}] 最終決済: {curr_p}円 (シミュレーション完了)")
                    is_position = False
                    
                if remaining_lots <= 0:
                    is_position = False

            # 画面表示
            if is_position:
                status = f"{pos_type}({remaining_lots}枚)"
            elif is_ordering:
                status = f"指値待機中({order_price}円 待ち:{queue_volume}枚)"
            else:
                status = "待機中"
                
            print(f"\r[{update_t}] 価格:{curr_p} 出来高:{total_v} 状態:{status} ", end="")
            
            # 連続エントリー防止のため、非保有・非注文時のみトリガーを有効に
            if not is_position and not is_ordering:
                pass
            else:
                trigger_action = None 

            time.sleep(0.5)

    finally:
        # 終了時にファイルを日付付きでバックアップ
        today_str = datetime.now().strftime("%Y%m%d_%H%M")
        if os.path.exists("market_history.csv"):
            backup_name = f"market_history_{today_str}.csv"
            shutil.copy("market_history.csv", backup_name)
            print(f"\n★生データをバックアップしました: {backup_name}")
        
        listener.stop()
        print("プログラムを終了しました。")

if __name__ == "__main__":
    main()