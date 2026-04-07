"""Chay: python test_tools.py"""
from tools import search_flights, search_hotels, calculate_budget

def call(fn, *args, **kwargs):
    """Goi tool, tu dong xu ly LangChain wrapper."""
    if hasattr(fn, "invoke"):
        import inspect
        params = list(inspect.signature(
            fn.func if hasattr(fn, "func") else fn).parameters.keys())
        kw = {params[i]: v for i, v in enumerate(args)}
        kw.update(kwargs)
        return fn.invoke(kw)
    return fn(*args, **kwargs)

SEP = "=" * 55

tests = [
    ("search_flights: Ha Noi -> Da Nang",
     lambda: call(search_flights, "Ha Noi", "Da Nang")),
    ("search_flights: Ha Noi -> Phu Quoc",
     lambda: call(search_flights, "Ha Noi", "Phu Quoc")),
    ("search_flights: reverse lookup (Da Nang -> Ha Noi)",
     lambda: call(search_flights, "Da Nang", "Ha Noi")),
    ("search_flights: not found (Ha Noi -> Can Tho)",
     lambda: call(search_flights, "Ha Noi", "Can Tho")),
    ("search_hotels: Phu Quoc, tat ca",
     lambda: call(search_hotels, "Phu Quoc")),
    ("search_hotels: Da Nang, max 500.000d",
     lambda: call(search_hotels, "Da Nang", 500_000)),
    ("search_hotels: Da Nang, max 100.000d (khong co ket qua)",
     lambda: call(search_hotels, "Da Nang", 100_000)),
    ("calculate_budget: 5tr - ve bay - khach san",
     lambda: call(calculate_budget, 5_000_000, "ve_bay:1100000,khach_san:1600000")),
    ("calculate_budget: vuot ngan sach",
     lambda: call(calculate_budget, 2_000_000, "ve_bay:1100000,khach_san:1600000")),
    ("calculate_budget: sai format (no colon)",
     lambda: call(calculate_budget, 5_000_000, "ve_bay_890000")),
]

for label, fn in tests:
    print(f"\n{SEP}\n{label}\n{SEP}")
    print(fn())

print(f"\n{SEP}\nAll {len(tests)} tests done!\n{SEP}")