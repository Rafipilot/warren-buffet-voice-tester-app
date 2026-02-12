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

options = [
    {
    "name":"Buffet",
    "model":"openai/gpt-oss-120b",
    "path":"tinker://72838a4a-7999-5480-8fb5-ece27454dbbe:train:0/sampler_weights/stage2-WBV-1.2-openai_gpt-oss-120b" ,  
    },
    {
    "name":"moonshotai/Kimi-K2-Thinking",
    "model":"openai/gpt-oss-120b",
    "path":"tinker://dbb4b782-d6ff-549b-87d0-20ce82230fc4:train:0/sampler_weights/WBV-stage2-Kimik2" ,  
    },
        {
    "name":"Cramer",
    "model":"openai/gpt-oss-120b",
    "path":"tinker://3734fd39-f9d7-58a6-bc80-d17d75ca44ee:train:0/sampler_weights/Cramer-stage2-GPT-OSS-120B" ,  
    },
]


tinker_api_key = getenv("TINKER_API_KEY")
openai_client = OpenAI(base_url="https://tinker.thinkingmachines.dev/services/tinker-prod/oai/api/v1", api_key=tinker_api_key)



os.environ["TINKER_API_KEY"] = os.getenv("TINKER_API_KEY") or st.secrets["env"]["TINKER_API_KEY"]
os.environ["ANTHROPIC_API_KEY"] = os.getenv("ANTHROPIC_API_KEY") or st.secrets["env"]["ANTHROPIC_API_KEY"]

anthropic_client = anthropic.Anthropic()


service_client = tinker.ServiceClient()

# s2 llama  tinker://027432d8-f086-57e2-bdeb-bbbab7db7ea3:train:0/weights/WBV-meta-llama-8B-stage-2-v1.12
# s2 gpt-oss tinker://72838a4a-7999-5480-8fb5-ece27454dbbe:train:0/weights/stage2-WBV-1.2-openai_gpt-oss-120b

chosen = st.selectbox("Chose which model you would like to use : ", options)

model_type = chosen["model"]

if model_type == "openai/gpt-oss-120b":
    st.session_state.sampling_path_base = "tinker://2c53387c-5ef6-58cd-8dde-fc35f3d98d9f:train:0/sampler_weights/base_model_weights"
elif model_type == "moonshotai/Kimi-K2-Thinking":
    st.session_state.sampling_path_base = "tinker://a277ebb0-efc8-50a5-9838-2f95224dd66e:train:0/sampler_weights/base_model_weights"



if chosen["name"] == "Buffet":
    from prompts.buffet_prompts import system_prompt, JUDGE_SYSTEM_PROMPT
elif chosen["name"] == "Cramer":
    from prompts.cramer import system_prompt, JUDGE_SYSTEM_PROMPT

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

        future_lora = execurtor.submit(call_model, chosen["path"])
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
