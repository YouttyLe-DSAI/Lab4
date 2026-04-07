from __future__ import annotations

from langchain_core.tools import tool
import logging
import unicodedata
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)

# ================================================================
# MOCK DATA
# ================================================================
FLIGHTS_DB = {
    ("Ha Noi", "Da Nang"): [
        {"airline": "Vietnam Airlines", "departure": "06:00", "arrival": "07:20", "price": 1_450_000, "class": "economy"},
        {"airline": "Vietnam Airlines", "departure": "14:00", "arrival": "15:20", "price": 2_800_000, "class": "business"},
        {"airline": "VietJet Air", "departure": "08:30", "arrival": "09:50", "price": 890_000, "class": "economy"},
        {"airline": "Bamboo Airways", "departure": "11:00", "arrival": "12:20", "price": 1_200_000, "class": "economy"},
    ],
    ("Ha Noi", "Phu Quoc"): [
        {"airline": "Vietnam Airlines", "departure": "07:00", "arrival": "09:15", "price": 2_100_000, "class": "economy"},
        {"airline": "VietJet Air", "departure": "10:00", "arrival": "12:15", "price": 1_350_000, "class": "economy"},
        {"airline": "VietJet Air", "departure": "16:00", "arrival": "18:15", "price": 1_100_000, "class": "economy"},
    ],
    ("Ha Noi", "Ho Chi Minh"): [
        {"airline": "Vietnam Airlines", "departure": "06:00", "arrival": "08:10", "price": 1_600_000, "class": "economy"},
        {"airline": "VietJet Air", "departure": "07:30", "arrival": "09:40", "price": 950_000, "class": "economy"},
        {"airline": "Bamboo Airways", "departure": "12:00", "arrival": "14:10", "price": 1_300_000, "class": "economy"},
        {"airline": "Vietnam Airlines", "departure": "18:00", "arrival": "20:10", "price": 3_200_000, "class": "business"},
    ],
    ("Ho Chi Minh", "Da Nang"): [
        {"airline": "Vietnam Airlines", "departure": "09:00", "arrival": "10:20", "price": 1_300_000, "class": "economy"},
        {"airline": "VietJet Air", "departure": "13:00", "arrival": "14:20", "price": 780_000, "class": "economy"},
    ],
    ("Ho Chi Minh", "Phu Quoc"): [
        {"airline": "Vietnam Airlines", "departure": "08:00", "arrival": "09:00", "price": 1_100_000, "class": "economy"},
        {"airline": "VietJet Air", "departure": "15:00", "arrival": "16:00", "price": 650_000, "class": "economy"},
    ],
}

HOTELS_DB = {
    "Da Nang": [
        {"name": "Muong Thanh Luxury", "stars": 5, "price_per_night": 1_800_000, "area": "My Khe", "rating": 4.5},
        {"name": "Sala Danang Beach", "stars": 4, "price_per_night": 1_200_000, "area": "My Khe", "rating": 4.3},
        {"name": "Fivitel Danang", "stars": 3, "price_per_night": 650_000, "area": "Son Tra", "rating": 4.1},
        {"name": "Memory Hostel", "stars": 2, "price_per_night": 250_000, "area": "Hai Chau", "rating": 4.6},
        {"name": "Christina Homestay", "stars": 2, "price_per_night": 350_000, "area": "An Thuong", "rating": 4.7},
    ],
    "Phu Quoc": [
        {"name": "Vinpearl Resort", "stars": 5, "price_per_night": 3_500_000, "area": "Bai Dai", "rating": 4.4},
        {"name": "Sol by Melia", "stars": 4, "price_per_night": 1_500_000, "area": "Bai Truong", "rating": 4.2},
        {"name": "Lahana Resort", "stars": 3, "price_per_night": 800_000, "area": "Duong Dong", "rating": 4.0},
        {"name": "9Station Hostel", "stars": 2, "price_per_night": 200_000, "area": "Duong Dong", "rating": 4.5},
    ],
    "Ho Chi Minh": [
        {"name": "Rex Hotel", "stars": 5, "price_per_night": 2_800_000, "area": "Quan 1", "rating": 4.3},
        {"name": "Liberty Central", "stars": 4, "price_per_night": 1_400_000, "area": "Quan 1", "rating": 4.1},
        {"name": "Cochin Zen Hotel", "stars": 3, "price_per_night": 550_000, "area": "Quan 3", "rating": 4.4},
        {"name": "The Common Room", "stars": 2, "price_per_night": 180_000, "area": "Quan 1", "rating": 4.6},
    ],
}

TRAVEL_TIPS_DB = {
    "Da Nang": {
        "best_time": "Thang 2-8, troi dep va it mua",
        "must_eat": ["Mi Quang", "Bun cha ca", "Banh xeo", "Hai san My Khe"],
        "must_visit": ["Bien My Khe", "Ban dao Son Tra", "Ba Na Hills"],
        "transport": "Grab hoac thue xe may 100k-150k/ngay",
        "saving_tip": "O khu An Thuong hoac Hai Chau thuong mem hon khu bien",
    },
    "Phu Quoc": {
        "best_time": "Thang 11-4, bien em va nang dep",
        "must_eat": ["Goi ca trich", "Bun quay", "Hai san nuong", "Banh canh cha ca"],
        "must_visit": ["Bai Sao", "Hon Thom", "Cho dem Dinh Cau"],
        "transport": "Nen thue xe may neu di nhieu diem",
        "saving_tip": "Dat phong khu Duong Dong de tiet kiem hon resort ven bien",
    },
    "Ho Chi Minh": {
        "best_time": "Thang 12-4, mua kho",
        "must_eat": ["Com tam", "Banh mi", "Hu tieu", "Oc dem"],
        "must_visit": ["Cho Ben Thanh", "Nha tho Duc Ba", "Pho di bo Nguyen Hue"],
        "transport": "Grab nhanh va tien, xe buyt re",
        "saving_tip": "An o quan dia phuong se re hon khu du lich trung tam",
    },
}

CITY_PROFILE_DB = {
    "Da Nang": {
        "style": "bien, de di, hop gia dinh va cap doi",
        "budget_level": "de tho hon Phu Quoc",
        "strong_points": "am thuc, bien, di chuyen de, chi phi can bang",
        "best_for": "nghi ngan ngay, budget vua phai, lan dau di bien",
    },
    "Phu Quoc": {
        "style": "dao bien, nghi duong, canh dep",
        "budget_level": "cao hon Da Nang",
        "strong_points": "bien dep, resort, trai nghiem nghi duong",
        "best_for": "honeymoon, resort, nghi duong 3-4 ngay",
    },
    "Ho Chi Minh": {
        "style": "do thi, an choi, am thuc",
        "budget_level": "linh hoat, nhieu muc gia",
        "strong_points": "do an da dang, nightlife, mua sam",
        "best_for": "city break, an uong, cong tac ket hop du lich",
    },
}

# ================================================================
# HELPERS
# ================================================================
_ALIASES = {
    "ha noi": "Ha Noi",
    "hanoi": "Ha Noi",
    "hn": "Ha Noi",
    "hà nội": "Ha Noi",

    "da nang": "Da Nang",
    "danang": "Da Nang",
    "dn": "Da Nang",
    "đà nẵng": "Da Nang",

    "phu quoc": "Phu Quoc",
    "phuquoc": "Phu Quoc",
    "pq": "Phu Quoc",
    "phú quốc": "Phu Quoc",

    "ho chi minh": "Ho Chi Minh",
    "hcm": "Ho Chi Minh",
    "sai gon": "Ho Chi Minh",
    "saigon": "Ho Chi Minh",
    "tp hcm": "Ho Chi Minh",
    "hồ chí minh": "Ho Chi Minh",
}

def _strip_accents(text: str) -> str:
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return text.replace("đ", "d").replace("Đ", "D")

def _norm_city(name: str) -> str:
    raw = (name or "").strip()
    if not raw:
        return ""
    key = raw.lower().strip()
    if key in _ALIASES:
        return _ALIASES[key]
    key2 = _strip_accents(key)
    return _ALIASES.get(key2, raw.strip().title())

def _fmt_money(amount: int) -> str:
    return f"{amount:,}d".replace(",", ".")

def _sort_flights(items: List[dict], sort_by: str) -> List[dict]:
    if sort_by == "departure":
        return sorted(items, key=lambda x: x["departure"])
    return sorted(items, key=lambda x: x["price"])

def _sort_hotels(items: List[dict], sort_by: str) -> List[dict]:
    if sort_by == "price":
        return sorted(items, key=lambda x: (x["price_per_night"], -x["rating"]))
    return sorted(items, key=lambda x: (-x["rating"], x["price_per_night"]))

def _safe_limit(limit: int) -> int:
    if limit <= 0:
        return 3
    return min(limit, 5)

def _parse_expenses(expenses: str) -> Dict[str, int]:
    result: Dict[str, int] = {}
    if not expenses or not expenses.strip():
        return result

    for raw_item in expenses.split(","):
        item = raw_item.strip()
        if not item:
            continue
        if ":" not in item:
            raise ValueError(
                f"Khoan chi '{item}' sai dinh dang. Dung dang 'ten:so_tien'."
            )
        name, amount_str = item.split(":", 1)
        name = name.strip().replace("_", " ")
        amount = int(amount_str.strip())
        if amount < 0:
            raise ValueError(f"So tien cua '{name}' khong duoc am.")
        result[name] = amount
    return result

def _find_route(origin: str, destination: str) -> Tuple[str, str, List[dict], bool]:
    o = _norm_city(origin)
    d = _norm_city(destination)
    flights = FLIGHTS_DB.get((o, d))
    reverse_used = False

    if not flights:
        reverse = FLIGHTS_DB.get((d, o))
        if reverse:
            flights = reverse
            reverse_used = True

    return o, d, flights or [], reverse_used

def _get_hotel_candidates(city: str, max_price_per_night: int, min_stars: int) -> List[dict]:
    c = _norm_city(city)
    hotels = HOTELS_DB.get(c, [])
    filtered = [
        h for h in hotels
        if h["price_per_night"] <= max_price_per_night and h["stars"] >= min_stars
    ]
    return filtered

# ================================================================
# TOOLS
# ================================================================
@tool
def search_flights(
    origin: str,
    destination: str,
    sort_by: str = "price",
    limit: int = 3,
) -> str:
    """
    Tim chuyen bay giua hai thanh pho.
    Toi uu token: chi tra ve mot so ket qua dau tien, co sort va summary.
    sort_by: 'price' hoac 'departure'
    limit: toi da 5 ket qua
    """
    try:
        o, d, flights, reverse_used = _find_route(origin, destination)
        if not o or not d:
            return "ERR|Thieu thong tin origin hoac destination."
        if not flights:
            return f"NO_FLIGHTS|{o}|{d}"

        sort_by = sort_by if sort_by in {"price", "departure"} else "price"
        limit = _safe_limit(limit)
        flights = _sort_flights(flights, sort_by)
        selected = flights[:limit]
        cheapest = min(flights, key=lambda x: x["price"])

        lines = [f"FLIGHTS|{o}|{d}|total={len(flights)}|sorted={sort_by}|reverse={reverse_used}"]
        for idx, f in enumerate(selected, 1):
            lines.append(
                f"{idx}|{f['airline']}|{f['departure']}-{f['arrival']}|{_fmt_money(f['price'])}|{f['class']}"
            )
        lines.append(
            f"CHEAPEST|{cheapest['airline']}|{cheapest['departure']}-{cheapest['arrival']}|{_fmt_money(cheapest['price'])}|{cheapest['class']}"
        )

        logger.info("search_flights(%s, %s) -> %d result(s)", o, d, len(selected))
        return "\n".join(lines)
    except Exception as e:
        logger.exception("search_flights error")
        return f"ERR|search_flights|{e}"

@tool
def search_hotels(
    city: str,
    max_price_per_night: int = 99_999_999,
    min_stars: int = 0,
    sort_by: str = "rating",
    limit: int = 3,
) -> str:
    """
    Tim khach san theo thanh pho, gia toi da, so sao toi thieu.
    sort_by: 'rating' hoac 'price'
    limit: toi da 5 ket qua
    """
    try:
        c = _norm_city(city)
        if not c:
            return "ERR|Thieu city."

        hotels = HOTELS_DB.get(c)
        if not hotels:
            return f"NO_HOTELS_CITY|{c}"

        filtered = _get_hotel_candidates(c, max_price_per_night, min_stars)
        if not filtered:
            return f"NO_HOTELS_MATCH|{c}|max={_fmt_money(max_price_per_night)}|min_stars={min_stars}"

        sort_by = sort_by if sort_by in {"rating", "price"} else "rating"
        limit = _safe_limit(limit)
        ranked = _sort_hotels(filtered, sort_by)[:limit]
        cheapest = min(filtered, key=lambda x: x["price_per_night"])
        best_rated = max(filtered, key=lambda x: (x["rating"], -x["price_per_night"]))

        lines = [
            f"HOTELS|{c}|matched={len(filtered)}|sorted={sort_by}|max={_fmt_money(max_price_per_night)}|min_stars={min_stars}"
        ]
        for idx, h in enumerate(ranked, 1):
            lines.append(
                f"{idx}|{h['name']}|{h['stars']}s|{h['area']}|{_fmt_money(h['price_per_night'])}/night|rating={h['rating']}"
            )
        lines.append(
            f"CHEAPEST|{cheapest['name']}|{_fmt_money(cheapest['price_per_night'])}/night"
        )
        lines.append(
            f"BEST_RATED|{best_rated['name']}|rating={best_rated['rating']}|{_fmt_money(best_rated['price_per_night'])}/night"
        )

        logger.info("search_hotels(%s) -> %d result(s)", c, len(ranked))
        return "\n".join(lines)
    except Exception as e:
        logger.exception("search_hotels error")
        return f"ERR|search_hotels|{e}"

@tool
def calculate_budget(total_budget: int, expenses: str) -> str:
    """
    Tinh tong chi, so tien con lai, va canh bao neu vuot ngan sach.
    expenses format: 've_bay:890000,khach_san:650000'
    """
    try:
        if total_budget < 0:
            return "ERR|Tong ngan sach khong duoc am."

        expense_dict = _parse_expenses(expenses)
        total_spent = sum(expense_dict.values())
        remaining = total_budget - total_spent
        status = "OK" if remaining >= 0 else "OVER"

        lines = [
            f"BUDGET|total={_fmt_money(total_budget)}|spent={_fmt_money(total_spent)}|remaining={_fmt_money(abs(remaining))}|status={status}"
        ]
        for name, amount in expense_dict.items():
            lines.append(f"ITEM|{name}|{_fmt_money(amount)}")

        if status == "OVER":
            lines.append(f"WARNING|Vuot ngan sach {_fmt_money(abs(remaining))}")
        elif remaining < 500_000:
            lines.append(f"WARNING|Ngan sach con lai rat eo hep: {_fmt_money(remaining)}")
        else:
            lines.append(f"INFO|Con lai {_fmt_money(remaining)}")

        logger.info(
            "calculate_budget(total=%s, spent=%s, status=%s)",
            _fmt_money(total_budget),
            _fmt_money(total_spent),
            status,
        )
        return "\n".join(lines)
    except ValueError as e:
        return f"ERR|calculate_budget|{e}"
    except Exception as e:
        logger.exception("calculate_budget error")
        return f"ERR|calculate_budget|{e}"

@tool
def get_travel_tips(city: str) -> str:
    """
    Lay tips du lich gon, tranh output qua dai de tiet kiem token.
    """
    try:
        c = _norm_city(city)
        tips = TRAVEL_TIPS_DB.get(c)
        if not tips:
            return f"NO_TIPS|{c}"

        lines = [
            f"TIPS|{c}",
            f"BEST_TIME|{tips['best_time']}",
            f"MUST_EAT|{', '.join(tips['must_eat'][:3])}",
            f"MUST_VISIT|{', '.join(tips['must_visit'][:3])}",
            f"TRANSPORT|{tips['transport']}",
            f"SAVING|{tips['saving_tip']}",
        ]
        logger.info("get_travel_tips(%s) OK", c)
        return "\n".join(lines)
    except Exception as e:
        logger.exception("get_travel_tips error")
        return f"ERR|get_travel_tips|{e}"

@tool
def compare_destinations(city1: str, city2: str) -> str:
    """
    So sanh 2 diem den de model co the tu van nhanh ma khong phai goi qua nhieu tool.
    """
    try:
        c1 = _norm_city(city1)
        c2 = _norm_city(city2)

        p1 = CITY_PROFILE_DB.get(c1)
        p2 = CITY_PROFILE_DB.get(c2)
        if not p1 or not p2:
            return f"NO_COMPARE|{c1}|{c2}"

        lines = [
            f"COMPARE|{c1}|{c2}",
            f"{c1}|style={p1['style']}|budget={p1['budget_level']}|best_for={p1['best_for']}",
            f"{c2}|style={p2['style']}|budget={p2['budget_level']}|best_for={p2['best_for']}",
            f"STRENGTHS|{c1}|{p1['strong_points']}",
            f"STRENGTHS|{c2}|{p2['strong_points']}",
        ]
        logger.info("compare_destinations(%s, %s) OK", c1, c2)
        return "\n".join(lines)
    except Exception as e:
        logger.exception("compare_destinations error")
        return f"ERR|compare_destinations|{e}"

@tool
def recommend_trip_bundle(
    origin: str,
    destination: str,
    nights: int,
    total_budget: int,
) -> str:
    """
    Super-tool de giam so lan goi tool:
    - Tim ve re nhat
    - Tinh budget con lai
    - Tim 1 option khach san tiet kiem + 1 option value
    - Tra ve ket qua compact cho LLM tong hop
    """
    try:
        if nights <= 0:
            return "ERR|So dem phai lon hon 0."
        if total_budget <= 0:
            return "ERR|Tong budget phai lon hon 0."

        o, d, flights, reverse_used = _find_route(origin, destination)
        if not flights:
            return f"NO_BUNDLE_FLIGHTS|{o}|{d}"

        cheapest_flight = min(flights, key=lambda x: x["price"])
        remaining_after_flight = total_budget - cheapest_flight["price"]
        if remaining_after_flight <= 0:
            return (
                f"BUNDLE|{o}|{d}|status=OVER\n"
                f"FLIGHT|{cheapest_flight['airline']}|{cheapest_flight['departure']}-{cheapest_flight['arrival']}|{_fmt_money(cheapest_flight['price'])}\n"
                f"WARNING|Tien ve da vuot hoac cham tran ngan sach"
            )

        max_hotel_per_night = max(0, remaining_after_flight // nights)
        hotels = _get_hotel_candidates(d, max_hotel_per_night, 0)

        if not hotels:
            return (
                f"BUNDLE|{o}|{d}|status=NO_HOTEL_MATCH|reverse={reverse_used}\n"
                f"FLIGHT|{cheapest_flight['airline']}|{cheapest_flight['departure']}-{cheapest_flight['arrival']}|{_fmt_money(cheapest_flight['price'])}\n"
                f"HOTEL_BUDGET_CAP|{_fmt_money(max_hotel_per_night)}/night\n"
                f"WARNING|Khong co khach san nao phu hop ngan sach con lai"
            )

        budget_hotel = min(hotels, key=lambda x: x["price_per_night"])
        value_hotel = max(hotels, key=lambda x: (x["rating"], -x["price_per_night"]))

        budget_total = cheapest_flight["price"] + budget_hotel["price_per_night"] * nights
        value_total = cheapest_flight["price"] + value_hotel["price_per_night"] * nights

        budget_status = "OK" if budget_total <= total_budget else "OVER"
        value_status = "OK" if value_total <= total_budget else "OVER"

        lines = [
            f"BUNDLE|{o}|{d}|nights={nights}|budget={_fmt_money(total_budget)}|reverse={reverse_used}",
            f"FLIGHT|{cheapest_flight['airline']}|{cheapest_flight['departure']}-{cheapest_flight['arrival']}|{_fmt_money(cheapest_flight['price'])}|{cheapest_flight['class']}",
            f"HOTEL_BUDGET_CAP|{_fmt_money(max_hotel_per_night)}/night",
            f"OPTION_BUDGET|{budget_hotel['name']}|{budget_hotel['stars']}s|{budget_hotel['area']}|{_fmt_money(budget_hotel['price_per_night'])}/night|total={_fmt_money(budget_total)}|status={budget_status}",
            f"OPTION_VALUE|{value_hotel['name']}|{value_hotel['stars']}s|{value_hotel['area']}|{_fmt_money(value_hotel['price_per_night'])}/night|total={_fmt_money(value_total)}|status={value_status}",
        ]

        remain_budget = total_budget - budget_total
        if remain_budget < 0:
            lines.append(f"WARNING|Vuot ngan sach toi thieu {_fmt_money(abs(remain_budget))}")
        elif remain_budget < 500_000:
            lines.append(f"WARNING|Con lai rat it: {_fmt_money(remain_budget)}")
        else:
            lines.append(f"INFO|Con lai neu chon option budget: {_fmt_money(remain_budget)}")

        logger.info("recommend_trip_bundle(%s, %s, %s dem) OK", o, d, nights)
        return "\n".join(lines)
    except Exception as e:
        logger.exception("recommend_trip_bundle error")
        return f"ERR|recommend_trip_bundle|{e}"