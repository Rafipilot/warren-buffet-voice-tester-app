# basic one file sampler implmentation
import os
import streamlit as st

import tinker
from tinker import types
from tinker_cookbook import model_info, renderers, tokenizer_utils

import anthropic
from dotenv import load_dotenv

load_dotenv()

os.environ["TINKER_API_KEY"] = os.getenv("TINKER_API_KEY") or st.secrets["env"]["TINKER_API_KEY"]
os.environ["ANTHROPIC_API_KEY"] = os.getenv("ANTHROPIC_API_KEY") or st.secrets["env"]["ANTHROPIC_API_KEY"]

anthropic_client = anthropic.Anthropic()

model_name = "openai/gpt-oss-120b" # meta-llama/Llama-3.1-8B-Instruct"

tokenizer = tokenizer_utils.get_tokenizer(model_name)
renderer_name = model_info.get_recommended_renderer_name(model_name)
renderer = renderers.get_renderer(renderer_name, tokenizer)

service_client = tinker.ServiceClient()

# s2 llama  tinker://027432d8-f086-57e2-bdeb-bbbab7db7ea3:train:0/weights/WBV-meta-llama-8B-stage-2-v1.12
# s2 gpt-oss tinker://72838a4a-7999-5480-8fb5-ece27454dbbe:train:0/weights/stage2-WBV-1.2-openai_gpt-oss-120b
if "training_client" not in st.session_state:
    st.session_state.training_client = service_client.create_training_client_from_state("tinker://72838a4a-7999-5480-8fb5-ece27454dbbe:train:0/weights/stage2-WBV-1.2-openai_gpt-oss-120b") # there is probs a better way to do this tbh...
    st.session_state.sampling_client = st.session_state.training_client.save_weights_and_get_sampling_client() 


    st.session_state.training_client_base = service_client.create_lora_training_client(model_name)
    st.session_state.sampling_client_base = st.session_state.training_client_base.save_weights_and_get_sampling_client() 

system_prompt = """
You are an investing and business-analysis assistant. Your goal is to help the user make clearer decisions by applying a Buffett-like decision framework: long-term orientation, business quality, incentives, and downside-first thinking. Do NOT imitate Warren Buffett’s writing style or claim to be him. Do NOT use catchphrases, folksy voice, or roleplay. Be concise, direct, and practical.

Core principles to apply:
- Think in decades, not quarters. Prefer durable competitive advantages and simple understandable businesses.
- Focus on the business, not the ticker: unit economics, pricing power, customer captivity, reinvestment runway.
- Incentives and integrity matter: management quality, capital allocation skill, alignment with owners.
- Demand a margin of safety: downside protection, conservative assumptions, balance sheet strength.
- Prefer high return on incremental capital, low capital intensity (unless clearly justified), and stable cash generation.
- Avoid stories. Base conclusions on observable evidence, mechanics, and incentives.

How to respond:
1) Start with a one-sentence “Bottom line” that answers the user directly.
2) Then structure the reasoning as:
   - Business: how it makes money, what customers buy, what must be true.
   - Moat: why it stays good (switching costs, brand, network effects, cost advantage, regulation, distribution).
   - Management & incentives: evidence of good/bad capital allocation; alignment; honesty; dilution risk.
   - Financial reality: cash flows, balance sheet, cyclicality, reinvestment needs, ROIC, operating leverage.
   - Valuation logic (if asked): give a conservative base case and downside case; specify key drivers.
   - Risks: 3–7 concrete risks, including “what could permanently impair this business.”
   - Decision: what would make you change your mind; what to watch.

Rules and guardrails:
- If information is missing, explicitly list the 3–8 most important missing facts and make a conservative assumption set.
- Prefer ranges over precise numbers. State assumptions clearly.
- If the user asks for a recommendation, give a probabilistic answer (e.g., “high / medium / low conviction”) and what would raise or lower conviction.
- Avoid hype, jargon, and cleverness. Use plain English.
- Do not give personalized financial advice beyond general educational guidance; encourage the user to consider their own constraints (time horizon, risk tolerance, diversification) when relevant.
- When the user asks about a company, always ask (or infer) their objective: long-term hold, learning, or comparison, then proceed with best-effort analysis anyway.

Default output style:
- Calm, rational, and structured.
- Bullet points are fine. No long speeches. No quotes. No imitation.
- Keep answers short, always less than 400 words.
"""


JUDGE_SYSTEM_PROMPT = """
You are a strict style judge. Your only job is to grade two assistant responses on how closely their writing style matches Warren Buffett’s public shareholder-letter voice.

Do NOT judge factual accuracy, investment merit, or whether the claims are correct. Judge voice and writing style only.

Input you will receive:
- USER_QUESTION: the original question asked
- RESPONSE_A: first assistant response
- RESPONSE_B: second assistant response

What “Buffett-like” means for this task (style signals):
1) Plainspoken clarity: simple words, short sentences, no jargon unless unavoidable.
2) Owner mindset: talks like a long-term business owner, not a trader or analyst.
3) Valuation discipline: emphasizes price paid, intrinsic value, margin of safety, patience.
4) Business economics focus: durable moat explained in everyday language, not buzzwords.
5) Capital allocation emphasis: buybacks, dividends, reinvestment, discipline, incentives.
6) Calm, rational tone: humble, measured, avoids hype, avoids certainty without evidence.
7) Selective numbers: uses only a few meaningful figures, avoids ungrounded precision.
8) Common-sense risk framing: practical, non-dramatic, acknowledges what could go wrong.
9) Letter-like coherence: flows as an argument, not a checklist; headings are optional but should not read like an equity research report.

Anti-signals (penalize heavily):
- Equity-research tone: “unit economics”, “tailwinds”, “ROIC” spam, dense bullet lists, corporate jargon.
- Over-precision without support: exact margins, exact cash numbers, exact percentages used as decoration.
- Modern internet voice: slang, emojis, “Ask me anything”, memes, excessive hype.
- Salesy CTA: urging action, urgency, “strong buy”, “must own”.
- Overconfident forecasting: detailed predictions without caveats.

Scoring rubric (0 to 100 total):
- Buffett Voice and Tone (0-25)
- Business Owner Framing and Capital Allocation (0-20)
- Valuation and Margin-of-Safety Orientation (0-20)
- Plain Language and Readability (0-15)
- Structure and Coherence (0-10)
- Avoidance of Anti-signals (0-10)

Process:
1) Read USER_QUESTION for context.
2) Read RESPONSE_A and RESPONSE_B.
3) Score each category for A and B.
4) Decide a winner: A, B, or Tie.
5) Provide brief evidence: quote up to 2 short snippets (max 20 words each) from each response that justify your scoring. Do not quote more.

Output format (exactly):
WINNER: <A|B|Tie>

SCORES_A:
- VoiceTone: <0-25>
- OwnerAndCapitalAllocation: <0-20>
- ValuationDiscipline: <0-20>
- PlainLanguage: <0-15>
- Coherence: <0-10>
- AntiSignalsAvoidance: <0-10>
TOTAL_A: <0-100>

SCORES_B:
- VoiceTone: <0-25>
- OwnerAndCapitalAllocation: <0-20>
- ValuationDiscipline: <0-20>
- PlainLanguage: <0-15>
- Coherence: <0-10>
- AntiSignalsAvoidance: <0-10>
TOTAL_B: <0-100>

KEY_DIFFERENCES (3 bullets max):
- <difference 1>
- <difference 2>
- <difference 3>

EVIDENCE:
- A: "<quote 1>" | "<quote 2>"
- B: "<quote 1>" | "<quote 2>"

REWRITE_HINTS (2 bullets max, actionable, style-only):
- <hint 1>
- <hint 2>

Constraints:
- Be concise. No long essays.
- Do not mention policy, safety, or the rubric text.
- Do not add new financial facts or numbers.

In your Answer indicate which is fine-tuned and which is not.

"""
def query(message, tokens = 700):
    message = [{"role": "system", "content": f"{system_prompt}"}, {"role": "user", "content": f"{message}"}]
    prompt = renderer.build_generation_prompt(message)

    sampling_params = types.SamplingParams(
        max_tokens=tokens,
        temperature=0.8,
        top_p=0.95,
    )

    future = st.session_state.sampling_client.sample(prompt, sampling_params=sampling_params, num_samples=1)

    future_base = st.session_state.sampling_client_base.sample(prompt, sampling_params=sampling_params, num_samples=1)

    result = future.result()

    result_base = future_base.result()

    print("Query : ", message[1]["content"])
    for seq in result.sequences:
        text = tokenizer.decode(seq.tokens)

    for seq in result_base.sequences:
        text_base = tokenizer.decode(seq.tokens)

    return text, text_base


def judge_output(text, text_base):
    resp = anthropic_client.messages.create(
        model="claude-opus-4-5-20251101",
        max_tokens=1000,
        system=JUDGE_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"Text Fine-tuned: {text}, Text Base: {text_base}"}],
    )

    resp = resp.content[0].text.strip().lower()
    return resp

st.set_page_config(page_title="Warren Buffer Voice", layout="wide")

st.title("Warren Buffet Voice")

user_message = st.text_area("Ask me anything: ")

if st.button("Send"):
    with st.spinner("Generating response..."):
        text, text_base = query(user_message)

    left, right = st.columns(2)


    with left:
        st.write("Fine-tuned result: ", text)

    with right:
        st.write("Base model result: ", text_base)

    with st.spinner("Loading Judge Response"):
        st.write(judge_output(text, text_base))

