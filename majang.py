import flet as ft
import ssl
import os
import socket

# SSL証明書エラー回避
ssl._create_default_https_context = ssl._create_unverified_context
from mahjong.hand_calculating.hand import HandCalculator
from mahjong.tile import TilesConverter
from mahjong.hand_calculating.hand_config import HandConfig
from mahjong.meld import Meld
from mahjong.constants import EAST, SOUTH, WEST, NORTH
from mahjong.hand_calculating.scores import ScoresCalculator

def get_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('10.255.255.255', 1))
        IP = s.getsockname()[0]
    except Exception:
        IP = '127.0.0.1'
    finally:
        s.close()
    return IP

def main(page: ft.Page):
    page.title = "Mahjong Master"
    page.theme_mode = ft.ThemeMode.DARK
    page.padding = 10
    page.scroll = "auto"
    
    # --- 状態管理 ---
    state = {
        "hand_tiles": [],
        "melds": [],
        "bakaze": EAST,
        "jikaze": SOUTH,
        "dora_count": 0,
        "current_palette": "m"
    }
    
    # --- UI要素 ---
    hand_row = ft.Row(wrap=True, spacing=4)
    meld_row = ft.Row(wrap=True, spacing=6)
    result_text = ft.Text(size=20, weight="bold", color=ft.Colors.AMBER_400)
    yaku_text = ft.Text(size=13, color=ft.Colors.GREY_300)
    waiting_tiles_row = ft.Row(wrap=True, spacing=4)
    waiting_container = ft.Container(
        content=ft.Column([
            ft.Text("💡 待ち牌候補:", weight="bold", size=12, color=ft.Colors.CYAN_200),
            waiting_tiles_row
        ]),
        visible=False, padding=8, bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.CYAN_700), border_radius=8
    )
    
    tiles_map = {
        "m": ["1", "2", "3", "4", "5", "6", "7", "8", "9"],
        "p": ["1", "2", "3", "4", "5", "6", "7", "8", "9"],
        "s": ["1", "2", "3", "4", "5", "6", "7", "8", "9"],
        "z": ["1", "2", "3", "4", "5", "6", "7"]
    }
    tile_names = {
        "m1": "一万", "m2": "二万", "m3": "三万", "m4": "四万", "m5": "五万", "m6": "六万", "m7": "七万", "m8": "八万", "m9": "九万",
        "p1": "一玉", "p2": "二玉", "p3": "三玉", "p4": "四玉", "p5": "五玉", "p6": "六玉", "p7": "七玉", "p8": "八玉", "p9": "九玉",
        "s1": "一竹", "s2": "二竹", "s3": "三竹", "s4": "四竹", "s5": "五竹", "s6": "六竹", "s7": "七竹", "s8": "八竹", "s9": "九竹",
        "z1": "東", "z2": "南", "z3": "西", "z4": "北", "z5": "白", "z6": "発", "z7": "中"
    }
    
    # Unicode 麻雀牌と漢字の組み合わせ (スマホでの強制絵文字化を回避)
    unicode_tiles = {
        "m1": "🀇\uFE0E", "m2": "🀈\uFE0E", "m3": "🀉\uFE0E", "m4": "🀊\uFE0E", "m5": "🀋\uFE0E", "m6": "🀌\uFE0E", "m7": "🀍\uFE0E", "m8": "🀎\uFE0E", "m9": "🀏\uFE0E",
        "p1": "🀙\uFE0E", "p2": "🀚\uFE0E", "p3": "🀛\uFE0E", "p4": "🀜\uFE0E", "p5": "🀝\uFE0E", "p6": "🀞\uFE0E", "p7": "🀟\uFE0E", "p8": "🀠\uFE0E", "p9": "🀡\uFE0E",
        "s1": "🀐\uFE0E", "s2": "🀑\uFE0E", "s3": "🀒\uFE0E", "s4": "🀓\uFE0E", "s5": "🀔\uFE0E", "s6": "🀕\uFE0E", "s7": "🀖\uFE0E", "s8": "🀗\uFE0E", "s9": "🀘\uFE0E",
        "z1": "東", "z2": "南", "z3": "西", "z4": "北", "z5": "白", "z6": "発", "z7": "中"
    }


    def update_hand_display():
        hand_row.controls.clear()
        for i, t in enumerate(state["hand_tiles"]):
            u_tile = unicode_tiles.get(t, "")
            # 漢字(字牌)の場合はサイズを少し調整して枠に収める
            f_size = 34 if t.startswith("z") else 48
            hand_row.controls.append(
                ft.Container(
                    content=ft.Text(u_tile, size=f_size, color=ft.Colors.BLACK, weight="bold" if t.startswith("z") else "normal"),
                    width=42, height=54, bgcolor=ft.Colors.WHITE, border_radius=4,
                    alignment=ft.Alignment(0, 0), on_click=lambda e, idx=i: remove_tile(idx),
                    border=ft.Border.all(1, ft.Colors.GREY_400)
                )
            )
        meld_row.controls.clear()
        for i, m in enumerate(state["melds"]):
            meld_texts = []
            for t in m["tiles"]:
                f_size = 28 if t.startswith("z") else 38
                meld_texts.append(ft.Text(unicode_tiles.get(t, t), size=f_size, color=ft.Colors.WHITE, weight="bold" if t.startswith("z") else "normal"))
            meld_row.controls.append(
                ft.Container(
                    content=ft.Row(meld_texts, spacing=-2),
                    padding=2, bgcolor=ft.Colors.BLUE_GREY_900, border_radius=6,
                    on_click=lambda e, idx=i: remove_meld(idx)
                )
            )
        update_waiting_tiles()
        page.update()

    def update_palette(t_type):
        state["current_palette"] = t_type
        palette_area.controls = [
            ft.Container(
                content=ft.Text(unicode_tiles.get(f"{t_type}{v}", ""), size=40 if t_type=="z" else 54, color=ft.Colors.BLACK, weight="bold" if t_type=="z" else "normal"),
                width=48, height=60, bgcolor=ft.Colors.WHITE, border_radius=6, alignment=ft.Alignment(0, 0),
                on_click=lambda e, v=v: add_tile(t_type, v), border=ft.Border.all(1, ft.Colors.GREY_300)
            ) for v in tiles_map[t_type]
        ]
        for btn in category_btns.controls:
            btn.style = ft.ButtonStyle(bgcolor=ft.Colors.AMBER_700 if btn.data == t_type else ft.Colors.GREY_900, color=ft.Colors.WHITE)
        page.update()

    def is_win_shape(c34):
        for h in range(34):
            if c34[h] >= 2:
                rem = list(c34); rem[h] -= 2
                if can_make_sets(rem): return True
        return False

    def can_make_sets(rem):
        for j in range(34):
            if rem[j] == 0: continue
            if rem[j] >= 3:
                rem2 = list(rem); rem2[j] -= 3
                if can_make_sets(rem2): return True
            if j < 27 and j % 9 < 7:
                if rem[j] > 0 and rem[j+1] > 0 and rem[j+2] > 0:
                    rem2 = list(rem); rem2[j] -= 1; rem2[j+1] -= 1; rem2[j+2] -= 1
                    if can_make_sets(rem2): return True
            return False
        return sum(rem) == 0

    def update_waiting_tiles():
        waiting_tiles_row.controls.clear()
        max_cl = 14 - (len(state["melds"]) * 3)
        if len(state["hand_tiles"]) == (max_cl - 1):
            try:
                c34 = [0]*34
                for t in state["hand_tiles"]:
                    idx = (0 if t[0] == 'm' else 9 if t[0] == 'p' else 18 if t[0] == 's' else 27) + (int(t[1]) - 1)
                    c34[idx] += 1
                total_c34 = list(c34)
                for m in state["melds"]:
                    for t in m["tiles"]:
                        idx = (0 if t[0] == 'm' else 9 if t[0] == 'p' else 18 if t[0] == 's' else 27) + (int(t[1]) - 1)
                        total_c34[idx] += 1
                found = False
                for i in range(34):
                    if total_c34[i] >= 4: continue
                    temp = list(c34); temp[i] += 1
                    if is_win_shape(temp):
                        ts = convert_34_to_str_local(i)
                        waiting_tiles_row.controls.append(
                            ft.Button(tile_names.get(ts, ts), on_click=lambda e, t=ts[0], v=ts[1]: add_tile(t, v), 
                                      style=ft.ButtonStyle(bgcolor=ft.Colors.CYAN_900, color=ft.Colors.WHITE))
                        )
                        found = True
                waiting_container.visible = found
            except: pass
        else: waiting_container.visible = False

    def convert_34_to_str_local(i):
        if i < 9: return f"m{i+1}"
        if i < 18: return f"p{i-8}"
        if i < 27: return f"s{i-17}"
        return f"z{i-26}"

    def add_tile(t_type, t_val):
        max_cl = 14 - (len(state["melds"]) * 3)
        if len(state["hand_tiles"]) < max_cl:
            state["hand_tiles"].append(f"{t_type}{t_val}")
            update_hand_display()

    def remove_tile(idx): state["hand_tiles"].pop(idx); update_hand_display()
    def remove_meld(idx): state["melds"].pop(idx); update_hand_display()

    def add_meld(m_type):
        if not state["hand_tiles"]: return
        base = state["hand_tiles"][-1]
        t_type, t_val = base[0], int(base[1])
        new_h = list(state["hand_tiles"])
        found = []
        if m_type == "pon" and new_h.count(base) >= 3:
            found = [base]*3
            for _ in range(3): new_h.remove(base)
        elif m_type == "kan" and new_h.count(base) >= 4:
            found = [base]*4
            for _ in range(4): new_h.remove(base)
        elif m_type == "chi" and t_type != 'z':
            for p in [[t_val-2, t_val-1, t_val], [t_val-1, t_val, t_val+1], [t_val, t_val+1, t_val+2]]:
                if all(1 <= v <= 9 for v in p):
                    target = [f"{t_type}{v}" for v in p]
                    if all(new_h.count(t) >= target.count(t) for t in set(target)):
                        found = target
                        for t in target: new_h.remove(t)
                        break
        if found:
            state["hand_tiles"] = new_h
            m_const = Meld.PON if m_type=="pon" else Meld.CHI if m_type=="chi" else Meld.KAN
            state["melds"].append({"type": m_const, "tiles": found})
            update_hand_display()

    def calculate_score(e):
        try:
            calculator = HandCalculator()
            dora_count = state["dora_count"]
            all_t = state["hand_tiles"] + [t for m in state["melds"] for t in m["tiles"]]
            c34 = [0]*34
            for t in state["hand_tiles"]:
                idx = (0 if t[0] == 'm' else 9 if t[0] == 'p' else 18 if t[0] == 's' else 27) + (int(t[1]) - 1)
                c34[idx] += 1
            m_s, p_s, s_s, h_s = "", "", "", ""
            for j in range(9): m_s += str(j+1)*c34[j]; p_s += str(j+1)*c34[9+j]; s_s += str(j+1)*c34[18+j]
            for j in range(7): h_s += str(j+1)*c34[27+j]
            c136 = TilesConverter.string_to_136_array(man=m_s, pin=p_s, sou=s_s, honors=h_s)
            win_tile = state["hand_tiles"][-1]
            win_base = (0 if win_tile[0] == 'm' else 9 if win_tile[0] == 'p' else 18 if win_tile[0] == 's' else 27) + (int(win_tile[1]) - 1)
            win136 = next((t for t in c136 if (t // 4) == win_base), None)
            melds = []
            moff = 100
            for m in state["melds"]:
                m_ids = []
                for t in m["tiles"]:
                    t_b = (0 if t[0] == 'm' else 9 if t[0] == 'p' else 18 if t[0] == 's' else 27) + (int(t[1]) - 1)
                    m_ids.append(t_b * 4 + (moff % 4)); moff += 1
                melds.append(Meld(meld_type=m["type"], tiles=m_ids, opened=True))
            config = HandConfig(
                is_tsumo=tsumo_switch.value, is_riichi=riichi_switch.value, is_ippatsu=ippatsu_switch.value,
                player_wind=state["jikaze"], round_wind=state["bakaze"]
            )
            result = HandCalculator().estimate_hand_value(c136, win136, melds=melds, config=config)
            is_win = is_win_shape(c34)
            if result.error == "hand_not_winning" and is_win: result.error = None
            if result.error:
                result_text.value = f"⚠️ {result.error}"; yaku_text.value = "形が不完全です"
            else:
                han = result.han or 0; fu = result.fu or 30
                y_list = [str(y) for y in result.yaku] if result.yaku else []
                yaku_trans = {
                    "Tanyao": "断幺九", "Chinitsu": "清一色", "Honitsu": "混一色", "Pinfu": "平和",
                    "Riichi": "立直", "Iipeiko": "一盃口", "Ippatsu": "一発", "Menzen Tsumo": "門前清自摸和",
                    "Yakuhai (chun)": "役牌(中)", "Yakuhai (haku)": "役牌(白)", "Yakuhai (hatsu)": "役牌(発)",
                    "Yakuhai (east)": "役牌(東)", "Yakuhai (south)": "役牌(南)", "Yakuhai (west)": "役牌(西)", "Yakuhai (north)": "役牌(北)",
                    "Double East": "ダブ東", "Double South": "ダブ南", "Chankan": "槍槓", "Rinshan Kaihou": "嶺上開花",
                    "Haitei Raoyue": "海底撈月", "Houtei Raoyui": "河底撈魚", "Double Riichi": "ダブル立直",
                    "Sanshoku Doujun": "三色同順", "Itsu": "一気通貫", "Toitoi": "対々和", "Sanankou": "三暗刻",
                    "Kokushi Musou": "国士無双", "Daisangen": "大三元", "Suuankou": "四暗刻", "Suuankou Tanki": "四暗刻単騎",
                    "Shousuushi": "小四喜", "Daisuushi": "大四喜", "Tsuuiisou": "字一色", "Chinroutoo": "清老頭",
                    "Ryuuiisou": "緑一色", "Chuuren Pooto": "九蓮宝燈", "Chuuren Pooto 9-machi": "純正九蓮宝燈",
                    "Suukantsu": "四槓子", "Tenhou": "天和", "Chihou": "地和", "Kokushi Musou 13-machi": "国士無双十三面待ち"
                }
                y_list_jp = [yaku_trans.get(y, y) for y in y_list]
                if dora_count > 0: han += dora_count; y_list_jp.append(f"ドラ{dora_count}")
                cost = result.cost
                if not cost and han > 0:
                    cost = ScoresCalculator().calculate_scores(han, fu, config, is_yakuman=han >= 13)
                if cost:
                    score_s = f"{cost['main']}点"
                    if tsumo_switch.value:
                        score_s = f"{cost['main']}オール" if state["jikaze"] == EAST else f"{cost['main']}/{cost['additional']}"
                    result_text.value = f"【{han}翻 {fu}符】 {score_s}"
                else: result_text.value = f"【{han}翻 {fu}符】 計算不可"
                yaku_text.value = "役: " + (", ".join(y_list_jp) if y_list_jp else "役なし")
        except Exception as ex: result_text.value = f"Error: {str(ex)}"
        page.update()

    wind_names = {EAST: "東 (親)", SOUTH: "南", WEST: "西", NORTH: "北"}
    dora_count_text = ft.Text("0", size=20, weight="bold", color=ft.Colors.AMBER_400)
    def change_dora(delta):
        state["dora_count"] = max(0, min(13, state["dora_count"] + delta))
        dora_count_text.value = str(state["dora_count"]); page.update()

    tsumo_switch = ft.Switch(label="ツモ", value=True, active_color=ft.Colors.AMBER_400)
    riichi_switch = ft.Switch(label="立直", value=False, active_color=ft.Colors.RED_400)
    ippatsu_switch = ft.Switch(label="一発", value=False, active_color=ft.Colors.BLUE_400)
    
    def set_wind(target, val): state[target] = val; update_ui_winds()
    def update_ui_winds():
        bakaze_btns.controls = [ft.Button(wind_names[w], on_click=lambda e, w=w: set_wind("bakaze", w), style=ft.ButtonStyle(bgcolor=ft.Colors.AMBER_700 if state["bakaze"]==w else ft.Colors.GREY_900, color=ft.Colors.WHITE)) for w in [EAST, SOUTH]]
        jikaze_btns.controls = [ft.Button(wind_names[w], on_click=lambda e, w=w: set_wind("jikaze", w), style=ft.ButtonStyle(bgcolor=ft.Colors.CYAN_700 if state["jikaze"]==w else ft.Colors.GREY_900, color=ft.Colors.WHITE)) for w in [EAST, SOUTH, WEST, NORTH]]
        page.update()

    bakaze_btns = ft.Row(spacing=5); jikaze_btns = ft.Row(spacing=5); update_ui_winds()
    palette_area = ft.Row(wrap=True, spacing=6)
    category_btns = ft.Row([
        ft.Button("万", data="m", on_click=lambda e: update_palette("m")),
        ft.Button("玉", data="p", on_click=lambda e: update_palette("p")),
        ft.Button("竹", data="s", on_click=lambda e: update_palette("s")),
        ft.Button("字", data="z", on_click=lambda e: update_palette("z")),
    ], spacing=5)
    
    def clear_all(e):
        state["hand_tiles"].clear(); state["melds"].clear(); state["dora_count"] = 0
        dora_count_text.value = "0"; tsumo_switch.value = True; riichi_switch.value = False; ippatsu_switch.value = False
        update_hand_display(); result_text.value = ""; yaku_text.value = ""; page.update()

    page.add(
        ft.Container(
            content=ft.Column([
                ft.Row([ft.Text("🀄️ Score Master", size=22, weight="bold", color=ft.Colors.AMBER_400), ft.IconButton(ft.Icons.REFRESH, on_click=clear_all)], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                ft.Column([
                    ft.Row([ft.Text("場:", size=12), bakaze_btns]),
                    ft.Row([ft.Text("自:", size=12), jikaze_btns]),
                    ft.Row([tsumo_switch, riichi_switch, ippatsu_switch], spacing=10),
                    ft.Row([ft.Text("ドラ:", size=12), ft.IconButton(ft.Icons.REMOVE_CIRCLE_OUTLINE, on_click=lambda _: change_dora(-1)), dora_count_text, ft.IconButton(ft.Icons.ADD_CIRCLE_OUTLINE, on_click=lambda _: change_dora(1))], spacing=0),
                ], spacing=8),
                ft.Divider(height=1, color=ft.Colors.GREY_800),
                ft.Text("牌を選択:", size=14, weight="bold"),
                category_btns,
                ft.Container(content=palette_area, padding=5, height=125),
                ft.Divider(height=1, color=ft.Colors.GREY_800),
                ft.Row([
                    ft.Button("ポン", on_click=lambda _: add_meld("pon"), bgcolor=ft.Colors.BLUE_900, color=ft.Colors.WHITE, expand=True),
                    ft.Button("チー", on_click=lambda _: add_meld("chi"), bgcolor=ft.Colors.GREEN_900, color=ft.Colors.WHITE, expand=True),
                    ft.Button("カン", on_click=lambda _: add_meld("kan"), bgcolor=ft.Colors.PURPLE_900, color=ft.Colors.WHITE, expand=True),
                ], spacing=5),
                ft.Text("手牌 (タップで削除):", size=14, weight="bold"),
                ft.Container(content=ft.Column([hand_row, meld_row], spacing=8), padding=10, bgcolor=ft.Colors.BLACK, border_radius=10, border=ft.Border.all(1, ft.Colors.GREY_900)),
                waiting_container,
                ft.Button("点数計算を実行", icon=ft.Icons.CALCULATE, on_click=calculate_score, bgcolor=ft.Colors.AMBER_700, color=ft.Colors.WHITE, height=55, width=1000),
                ft.Container(content=ft.Column([result_text, yaku_text], spacing=2), padding=12, bgcolor=ft.Colors.GREY_900, border_radius=10, border=ft.Border.all(1, ft.Colors.AMBER_900 if result_text.value else ft.Colors.GREY_800))
            ], spacing=10),
            padding=10
        )
    )
    update_palette("m")
    update_hand_display()

if __name__ == "__main__":
    my_ip = get_ip()
    print(f"Server starting on http://{my_ip}:8550")
    ft.app(target=main, port=8550, host="0.0.0.0", view=ft.AppView.WEB_BROWSER)
