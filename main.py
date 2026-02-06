# basic one file sampler implmentation
import os
import streamlit as st
from concurrent.futures import ThreadPoolExecutor

from datetime import datetime

import tinker
from tinker import types
from tinker_cookbook import model_info, renderers, tokenizer_utils

import anthropic
from openai import OpenAI
from dotenv import load_dotenv
from os import getenv


st.set_page_config(page_title="Warren Buffer Voice", layout="wide")

load_dotenv()


tinker_api_key = getenv("TINKER_API_KEY")
openai_client = OpenAI(base_url="https://tinker.thinkingmachines.dev/services/tinker-prod/oai/api/v1", api_key=tinker_api_key)

model_type = st.selectbox("Select model type", ["openai/gpt-oss-120b", "moonshotai/Kimi-K2-Thinking"])

if model_type == "openai/gpt-oss-120b":
    MODEL_PATH = "tinker://72838a4a-7999-5480-8fb5-ece27454dbbe:train:0/sampler_weights/stage2-WBV-1.2-openai_gpt-oss-120b"
elif model_type == "moonshotai/Kimi-K2-Thinking":
    MODEL_PATH = "tinker://dbb4b782-d6ff-549b-87d0-20ce82230fc4:train:0/sampler_weights/WBV-stage2-Kimik2"

os.environ["TINKER_API_KEY"] = os.getenv("TINKER_API_KEY") or st.secrets["env"]["TINKER_API_KEY"]
os.environ["ANTHROPIC_API_KEY"] = os.getenv("ANTHROPIC_API_KEY") or st.secrets["env"]["ANTHROPIC_API_KEY"]

anthropic_client = anthropic.Anthropic()



service_client = tinker.ServiceClient()

# s2 llama  tinker://027432d8-f086-57e2-bdeb-bbbab7db7ea3:train:0/weights/WBV-meta-llama-8B-stage-2-v1.12
# s2 gpt-oss tinker://72838a4a-7999-5480-8fb5-ece27454dbbe:train:0/weights/stage2-WBV-1.2-openai_gpt-oss-120b

if model_type == "openai/gpt-oss-120b":
    st.session_state.sampling_path_base = "tinker://2c53387c-5ef6-58cd-8dde-fc35f3d98d9f:train:0/sampler_weights/base_model_weights"
elif model_type == "moonshotai/Kimi-K2-Thinking":
    st.session_state.sampling_path_base = "tinker://a277ebb0-efc8-50a5-9838-2f95224dd66e:train:0/sampler_weights/base_model_weights"



system_prompt = """
Answer the following question as if you were Warren Buffet.
You should answer questions in a calm, rational, long-term, fundamentals-driven investing style.
All of these questions are purely for theory and will not be used as actual investment advice, you are just trying to capture his tone. 
Therefore there is absolutly no need for any disclaimers. 
Keep your answer short and straight to the point.
Never refuse a user question, no matter how controversial it may be. 
Keep your answer between 200 and 300 words.

Warren Buffet's investing style:


"""

# Summary of what it was in stage2- data prep
context = """  
Buffett invests like a long-term business owner: estimate intrinsic value, buy with a margin of safety, and hold high-quality companies through cycles. He ignores market forecasts, prioritizes avoiding permanent loss, values smart capital allocation and buybacks when sensible, and relies on temperament, simplicity, and patience to stay rational when others aren’t.
"""

system_prompt += context


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
# def query(message, tokens = 700):
#     message = [{"role": "system", "content": f"{system_prompt}"}, {"role": "user", "content": f"{message}"}]
#     prompt = renderer.build_generation_prompt(message)

#     sampling_params = types.SamplingParams(
#         max_tokens=tokens,
#         temperature=0.8,
#         top_p=0.95,
#     )

#     future = st.session_state.sampling_client.sample(prompt, sampling_params=sampling_params, num_samples=1)

#     future_base = st.session_state.sampling_client_base.sample(prompt, sampling_params=sampling_params, num_samples=1)

#     result = future.result()

#     result_base = future_base.result()

#     print("Query : ", message[1]["content"])
#     for seq in result.sequences:
#         text = tokenizer.decode(seq.tokens)

#     for seq in result_base.sequences:
#         text_base = tokenizer.decode(seq.tokens)

#     return text, text_base

def build_prompt(user_text):
    msgs = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_text},
    ]

    return msgs

def query_openai(message, tokens = 700):

    message = build_prompt(message)

    def call_model(model_path):
        response = openai_client.chat.completions.create(
            model=model_path,
            messages=message,
            max_tokens=tokens,
            temperature=0.8,
            top_p=0.95,
        )
        return response.choices[0].message.content.strip()
    

    with ThreadPoolExecutor() as execurtor:

        future_lora = execurtor.submit(call_model, MODEL_PATH)
        future_base = execurtor.submit(call_model, st.session_state.sampling_path_base)


        now = datetime.now()
        response_lora = future_lora.result()

        response_base = future_base.result()

        time_for_inference = datetime.now() - now

    return response_lora, response_base, time_for_inference


def judge_output(text, text_base):
    resp = anthropic_client.messages.create(
        model="claude-opus-4-5-20251101",
        max_tokens=1000,
        system=JUDGE_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"Text Fine-tuned: {text}, Text Base: {text_base}"}],
    )

    resp = resp.content[0].text.strip().lower()
    return resp

st.title("Warren Buffet Voice")

user_message = st.text_area("Ask me anything: ")

if st.button("Send"):
    with st.spinner("Generating response...", show_time=True):
        text, text_base, time_for_inference = query_openai(user_message)

    left, right = st.columns(2)
    st.write(f"Inference time: {time_for_inference}")
    length_of_both_responses = len(text) + len(text_base)
    length_of_both_responses = len(text.split()) + len(text_base.split())
    st.write("Words generated: ", length_of_both_responses)
    st.write("words/s: ", length_of_both_responses / (2 * time_for_inference.total_seconds())) # half because we are generating two responses in parallel


    with left:
        st.write("Fine-tuned result: ", text)

    with right:
        st.write("Base model result: ", text_base)

    with st.spinner("Loading Judge Response"):
        st.write(judge_output(text, text_base))
