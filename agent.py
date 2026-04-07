from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph import StateGraph, START
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from tools import (
    search_flights,
    search_hotels,
    calculate_budget,
    get_travel_tips,
    compare_destinations,
    recommend_trip_bundle,
)
from dotenv import load_dotenv
from dataclasses import dataclass
import logging
import time
import re


# ── Logging ────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


load_dotenv()


# ── Colors ─────────────────────────────────────────────────────────────────
try:
    from colorama import Fore, Style, init
    init(autoreset=True)
    C_USER    = Fore.CYAN + Style.BRIGHT
    C_BOT     = Fore.GREEN + Style.BRIGHT
    C_TOOL    = Fore.YELLOW
    C_INFO    = Fore.WHITE + Style.DIM
    C_RESET   = Style.RESET_ALL
    C_BORDER  = Fore.BLUE
    C_METRICS = Fore.MAGENTA
    C_COST    = Fore.RED + Style.BRIGHT
except ImportError:
    C_USER = C_BOT = C_TOOL = C_INFO = C_RESET = C_BORDER = C_METRICS = C_COST = ""


# ── Pricing: Gemini 2.5 Flash ──────────────────────────────────────────────
PRICE_INPUT_PER_TOKEN  = 0.30 / 1_000_000
PRICE_OUTPUT_PER_TOKEN = 2.50 / 1_000_000
USD_TO_VND             = 25_500

# Giới hạn số message mang vào LLM để giảm token
MAX_HISTORY_MESSAGES = 8


# ── Session Stats ──────────────────────────────────────────────────────────
@dataclass
class SessionStats:
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tool_calls: int = 0
    call_count: int = 0

    @property
    def cost_usd(self) -> float:
        return (
            self.total_input_tokens * PRICE_INPUT_PER_TOKEN
            + self.total_output_tokens * PRICE_OUTPUT_PER_TOKEN
        )

    @property
    def cost_vnd(self) -> int:
        return int(self.cost_usd * USD_TO_VND)

    def summary(self) -> str:
        return (
            f"LLM calls: {self.call_count} | "
            f"Tool calls: {self.total_tool_calls} | "
            f"Tokens: {self.total_input_tokens:,} in / {self.total_output_tokens:,} out | "
            f"Cost: ${self.cost_usd:.6f} (~{self.cost_vnd:,}d)"
        )


stats = SessionStats()
_call_meta: dict = {"latency_ms": 0.0, "input_tokens": 0, "output_tokens": 0}


# ── 1. System Prompt ───────────────────────────────────────────────────────
with open("system_prompt.txt", "r", encoding="utf-8") as f:
    SYSTEM_PROMPT = f.read()
logger.info("System prompt loaded (%d chars)", len(SYSTEM_PROMPT))


# ── 2. State ───────────────────────────────────────────────────────────────
class AgentState(TypedDict):
    messages: Annotated[list, add_messages]


# ── 3. LLM + Tools ─────────────────────────────────────────────────────────
tools_list = [
    search_flights,
    search_hotels,
    calculate_budget,
    get_travel_tips,
    compare_destinations,
    recommend_trip_bundle,
]

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    temperature=0.5,
)
llm_with_tools = llm.bind_tools(tools_list)

logger.info(
    "LLM (Gemini 2.5 Flash) + %d tools: %s",
    len(tools_list),
    [t.name for t in tools_list],
)


# ── 4. Fast Guardrails ─────────────────────────────────────────────────────
OFFTOPIC_KEYWORDS = {
    "python", "java", "c++", "code", "lập trình", "lap trinh", "linked list",
    "chính trị", "chinh tri", "tài chính", "tai chinh", "đầu tư", "dau tu",
    "chứng khoán", "chung khoan", "toán", "giai toan", "bài tập", "bai tap",
    "essay", "viết văn", "viet van", "hack", "virus", "malware", "sql",
}

TRAVEL_KEYWORDS = {
    "du lịch", "du lich", "vé", "ve", "vé máy bay", "ve may bay", "chuyến bay",
    "flight", "khách sạn", "khach san", "hotel", "resort", "homestay", "hostel",
    "đà nẵng", "da nang", "phú quốc", "phu quoc", "hà nội", "ha noi",
    "hồ chí minh", "ho chi minh", "sài gòn", "sai gon", "budget", "ngân sách",
    "ngan sach", "lịch trình", "lich trinh", "duy chuyển", "di chuyển", "đi đâu", "di dau",
}

SMALLTALK_PATTERNS = [
    r"^xin chào[!. ]*$",
    r"^chào[!. ]*$",
    r"^hello[!. ]*$",
    r"^hi[!. ]*$",
    r"^alo[!. ]*$",
    r"^bạn là ai\??$",
    r"^ban la ai\??$",
]

def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower().strip())

def is_smalltalk(text: str) -> bool:
    t = normalize_text(text)
    return any(re.match(p, t) for p in SMALLTALK_PATTERNS)

def is_obvious_offtopic(text: str) -> bool:
    t = normalize_text(text)
    if any(k in t for k in OFFTOPIC_KEYWORDS):
        if not any(k in t for k in TRAVEL_KEYWORDS):
            return True
    return False

def fast_response(text: str) -> str | None:
    t = normalize_text(text)

    if is_smalltalk(t):
        return (
            "Chào bạn, mình là TravelBuddy — trợ lý du lịch thông minh.\n"
            "Bạn muốn đi đâu, trong bao lâu và ngân sách khoảng bao nhiêu để mình tư vấn nhanh cho bạn nhé?"
        )

    if is_obvious_offtopic(t):
        return (
            "Mình chỉ hỗ trợ tư vấn du lịch, vé máy bay, khách sạn và lịch trình thôi nhé.\n"
            "Bạn cứ gửi điểm đến, số đêm hoặc ngân sách, mình sẽ lên phương án phù hợp."
        )

    return None


# ── 5. Helpers tối ưu context ──────────────────────────────────────────────
def trim_messages(messages: list) -> list:
    if not messages:
        return messages

    if isinstance(messages[0], SystemMessage):
        system_msg = messages[0]
        others = messages[1:]
        return [system_msg] + others[-MAX_HISTORY_MESSAGES:]
    return messages[-MAX_HISTORY_MESSAGES:]


def build_messages_with_system(messages: list) -> list:
    if not messages:
        return [SystemMessage(content=SYSTEM_PROMPT)]

    if isinstance(messages[0], SystemMessage):
        final_messages = messages
    else:
        final_messages = [SystemMessage(content=SYSTEM_PROMPT)] + messages

    return trim_messages(final_messages)


# ── 6. Agent Node ──────────────────────────────────────────────────────────
def agent_node(state: AgentState) -> dict:
    messages = build_messages_with_system(state["messages"])

    response = llm_with_tools.invoke(messages)
    stats.call_count += 1

    _call_meta["input_tokens"] = 0
    _call_meta["output_tokens"] = 0

    if hasattr(response, "usage_metadata") and response.usage_metadata:
        meta = response.usage_metadata
        inp = (
            getattr(meta, "input_tokens", None)
            or getattr(meta, "prompt_token_count", None)
            or 0
        )
        out = (
            getattr(meta, "output_tokens", None)
            or getattr(meta, "candidates_token_count", None)
            or 0
        )

        stats.total_input_tokens += inp
        stats.total_output_tokens += out
        _call_meta["input_tokens"] = inp
        _call_meta["output_tokens"] = out

        logger.info("Tokens — in: %d | out: %d", inp, out)

    if response.tool_calls:
        for tc in response.tool_calls:
            logger.info("Goi tool: %s(%s)", tc["name"], tc["args"])
    else:
        logger.info("Tra loi truc tiep")

    return {"messages": [response]}


# ── 7. Timed Tool Node ─────────────────────────────────────────────────────
_tool_node = ToolNode(tools_list)

def timed_tool_node(state: AgentState) -> dict:
    t0 = time.perf_counter()
    result = _tool_node.invoke(state)
    elapsed_ms = (time.perf_counter() - t0) * 1000
    _call_meta["latency_ms"] = elapsed_ms
    stats.total_tool_calls += 1
    logger.info("Tool latency: %.1f ms", elapsed_ms)
    return result


# ── 8. Graph ───────────────────────────────────────────────────────────────
builder = StateGraph(AgentState)
builder.add_node("agent", agent_node)
builder.add_node("tools", timed_tool_node)
builder.add_edge(START, "agent")
builder.add_conditional_edges("agent", tools_condition)
builder.add_edge("tools", "agent")
graph = builder.compile()

logger.info("Graph compiled: START -> agent <-> tools -> END")


# ── 9. UI Helpers ──────────────────────────────────────────────────────────
def get_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for part in content:
            if isinstance(part, dict) and "text" in part:
                parts.append(part["text"])
            elif isinstance(part, str):
                parts.append(part)
        return "\n".join(parts)
    return str(content)


def stream_print(text: str, delay: float = 0.008) -> None:
    for ch in text:
        print(ch, end="", flush=True)
        time.sleep(delay)
    print()


def print_step(
    step_type: str,
    content: str,
    color: str = "",
    show_metrics: bool = False,
    tool_name: str = "",
) -> None:
    icons = {
        "THOUGHT": " THOUGHT",
        "ACTION":  "  ACTION ",
        "OBSERVE": "  OBSERVE",
        "ANSWER":  " ANSWER ",
    }
    icon = icons.get(step_type, "•")
    border = "─" * 60

    print(f"\n{color}{border}")
    print(f"{icon} | {content[:80]}{'...' if len(content) > 80 else ''}")

    if len(content) > 80:
        for line in content[80:].splitlines():
            print(f"            {line}")

    if show_metrics and step_type == "ACTION":
        inp = _call_meta.get("input_tokens", 0)
        out = _call_meta.get("output_tokens", 0)
        cost_usd = inp * PRICE_INPUT_PER_TOKEN + out * PRICE_OUTPUT_PER_TOKEN
        cost_vnd = int(cost_usd * USD_TO_VND)
        print(
            f"{C_METRICS}            "
            f"📊 Tokens: {inp:,} in / {out:,} out  "
            f"| Cost: ${cost_usd:.6f} (~{cost_vnd}d)"
            f"{C_RESET}{color}"
        )

    if show_metrics and step_type == "OBSERVE":
        lat = _call_meta.get("latency_ms", 0.0)
        print(
            f"{C_METRICS}            "
            f"⏱  Tool: {tool_name or 'unknown':<22}"
            f"| Latency: {lat:6.0f} ms"
            f"{C_RESET}{color}"
        )

    print(f"{border}{C_RESET}")


def print_session_summary() -> None:
    border = "═" * 60
    print(f"\n{C_METRICS}{border}")
    print("  SESSION SUMMARY")
    print(f"  {stats.summary()}")
    print(f"{border}{C_RESET}")


# ── 10. Main Chat Loop ─────────────────────────────────────────────────────
def main():
    border = C_BORDER + "═" * 62 + C_RESET
    print(border)
    print(C_BOT  + "  TravelBuddy AI -- Tro ly Du lich Thong minh"         + C_RESET)
    print(C_INFO + "  Powered by Gemini 2.5 Flash + LangGraph (ReAct)"     + C_RESET)
    print(C_INFO + "  'quit' thoat | 'clear' reset | 'stats' xem chi phi"  + C_RESET)
    print(border)

    conversation_history: list = []

    while True:
        try:
            user_input = input(f"\n{C_USER}Ban: {C_RESET}").strip()
        except (EOFError, KeyboardInterrupt):
            print_session_summary()
            print(f"\n{C_INFO}Tam biet! Chuc chuyen di vui ve!{C_RESET}")
            break

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit", "q"):
            print_session_summary()
            print(f"{C_INFO}Tam biet!{C_RESET}")
            break

        if user_input.lower() == "clear":
            conversation_history.clear()
            print(f"{C_INFO}[Da xoa lich su hoi thoai]{C_RESET}")
            continue

        if user_input.lower() == "stats":
            print_session_summary()
            continue

        # Fast guardrail truoc khi goi LLM
        quick = fast_response(user_input)
        if quick is not None:
            print(f"\n{C_BOT}TravelBuddy:{C_RESET}")
            stream_print(quick, delay=0.004)
            continue

        conversation_history.append(HumanMessage(content=user_input))
        print(f"\n{C_INFO}[TravelBuddy dang xu ly...]{C_RESET}")

        try:
            final_answer = ""
            last_tool_name = ""

            for event in graph.stream(
                {"messages": conversation_history},
                stream_mode="updates",
            ):
                for node_name, node_output in event.items():
                    msgs = node_output.get("messages", [])

                    for msg in msgs:
                        if node_name == "agent":
                            if hasattr(msg, "tool_calls") and msg.tool_calls:
                                raw = get_text(msg.content)
                                if raw and raw.strip():
                                    print_step("THOUGHT", raw.strip(), C_INFO)

                                for tc in msg.tool_calls:
                                    last_tool_name = tc["name"]
                                    args_str = ", ".join(
                                        f"{k}={repr(v)}"
                                        for k, v in tc["args"].items()
                                    )
                                    print_step(
                                        "ACTION",
                                        f"{tc['name']}({args_str})",
                                        C_TOOL,
                                        show_metrics=True,
                                    )

                            elif msg.content:
                                final_answer = get_text(msg.content)

                        elif node_name == "tools":
                            if hasattr(msg, "content") and msg.content:
                                raw = get_text(msg.content)
                                preview = raw[:300]
                                suffix = "..." if len(raw) > 300 else ""
                                print_step(
                                    "OBSERVE",
                                    preview + suffix,
                                    C_INFO,
                                    show_metrics=True,
                                    tool_name=last_tool_name,
                                )

            if final_answer:
                print(f"\n{C_BOT}TravelBuddy:{C_RESET}")
                stream_print(final_answer, delay=0.008)
                print(
                    f"\n{C_METRICS}  [Session] "
                    f"Calls: {stats.call_count} | "
                    f"Tools: {stats.total_tool_calls} | "
                    f"Tokens: {stats.total_input_tokens:,} in / {stats.total_output_tokens:,} out | "
                    f"{C_COST}Cost: ${stats.cost_usd:.6f} (~{stats.cost_vnd:,}d)"
                    f"{C_RESET}"
                )
                conversation_history.append(AIMessage(content=final_answer))
            else:
                print(f"{C_INFO}(Khong co phan hoi){C_RESET}")

        except Exception as e:
            logger.error("Agent error: %s", e)
            print(f"\n{C_BOT}TravelBuddy:{C_RESET} Xin loi, co loi: {e}")


if __name__ == "__main__":
    main()