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
    "name":"Buffet",
    "model":"moonshotai/Kimi-K2-Thinking",
    "path":"tinker://dbb4b782-d6ff-549b-87d0-20ce82230fc4:train:0/sampler_weights/WBV-stage2-Kimik2" ,  
    },
        {
    "name":"Cramer",
    "model":"openai/gpt-oss-120b",
    "path":"tinker://3734fd39-f9d7-58a6-bc80-d17d75ca44ee:train:0/sampler_weights/Cramer-stage2-GPT-OSS-120B" ,  
    },
    {
        "name":"Munger",
        "model": "moonshotai/Kimi-K2-Thinking",
        "path": "tinker://bb6e01c2-38ce-510f-9721-0e3af4b5a941:train:0/sampler_weights/Munger-stage2-KimiK2"
    },
        {
        "name":"Soros",
        "model": "moonshotai/Kimi-K2-Thinking",
        "path": "tinker://487ce42d-0771-5dd8-869d-886e38f51055:train:0/sampler_weights/Soros-stage2-KimiK2"
    },

]

# keep your OpenAI-compatible client, but make sure key is set first
tinker_api_key = os.getenv("TINKER_API_KEY") or st.secrets["env"]["TINKER_API_KEY"]
os.environ["TINKER_API_KEY"] = tinker_api_key

anthropic_key = os.getenv("ANTHROPIC_API_KEY") or st.secrets["env"]["ANTHROPIC_API_KEY"]
os.environ["ANTHROPIC_API_KEY"] = anthropic_key 

openai_client = OpenAI(
    base_url="https://tinker.thinkingmachines.dev/services/tinker-prod/oai/api/v1",
    api_key=tinker_api_key,
)

anthropic_client = anthropic.Anthropic()

if "service_client" not in st.session_state:
    st.session_state.service_client = tinker.ServiceClient()

chosen = st.selectbox(
    "Chose which model you would like to use : ",
    options,
    format_func=lambda o: f'{o["name"]} | {o["model"]}',
)

model_type = chosen["model"]

def change_model():
    st.session_state.tokenizer = tokenizer_utils.get_tokenizer(model_type)
    st.session_state.renderer_name = model_info.get_recommended_renderer_name(model_type)
    st.session_state.renderer = renderers.get_renderer(st.session_state.renderer_name, st.session_state.tokenizer)

if "model_type" not in st.session_state:
    st.session_state.model_type = model_type
    change_model()
elif st.session_state.model_type != model_type:
    st.session_state.model_type = model_type
    change_model()
elif "tokenizer" not in st.session_state or "renderer" not in st.session_state:
    change_model()

if model_type == "openai/gpt-oss-120b":
    st.session_state.sampling_path_base = "tinker://2c53387c-5ef6-58cd-8dde-fc35f3d98d9f:train:0/sampler_weights/base_model_weights"
elif model_type == "moonshotai/Kimi-K2-Thinking":
    st.session_state.sampling_path_base = "tinker://a277ebb0-efc8-50a5-9838-2f95224dd66e:train:0/sampler_weights/base_model_weights"

if "sampling_client_path" not in st.session_state or st.session_state.sampling_client_path != chosen["path"]:
    st.session_state.sampling_client_path = chosen["path"]
    st.session_state.sampling_client = st.session_state.service_client.create_sampling_client(model_path=chosen["path"])

if "sampling_client_base_path" not in st.session_state or st.session_state.sampling_client_base_path != st.session_state.sampling_path_base:
    st.session_state.sampling_client_base_path = st.session_state.sampling_path_base
    st.session_state.sampling_client_base = st.session_state.service_client.create_sampling_client(
        model_path=st.session_state.sampling_path_base
    )

if chosen["name"] == "Buffet":
    from prompts.buffet_prompts import system_prompt, JUDGE_SYSTEM_PROMPT
elif chosen["name"] == "Cramer":
    from prompts.cramer import system_prompt, JUDGE_SYSTEM_PROMPT
elif chosen["name"] == "Munger":
    from prompts.munger import system_prompt, JUDGE_SYSTEM_PROMPT
elif chosen["name"] == "Soros":
    from prompts.soros import system_prompt, JUDGE_SYSTEM_PROMPT

def build_prompt(user_text):
    msgs = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_text},
    ]
    return msgs

def query(message, tokens=700):
    message = [{"role": "system", "content": f"{system_prompt}"}, {"role": "user", "content": f"{message}"}]
    prompt = st.session_state.renderer.build_generation_prompt(message)

    sampling_params = types.SamplingParams(
        max_tokens=tokens,
        temperature=0.8,
        top_p=0.95,
    )

    now = datetime.now()
    
    future = st.session_state.sampling_client.sample(prompt, sampling_params=sampling_params, num_samples=1)
    future_base = st.session_state.sampling_client_base.sample(prompt, sampling_params=sampling_params, num_samples=1)

    result = future.result()
    result_base = future_base.result()

    time_for_inference = datetime.now() - now

    print("Query : ", message[1]["content"])

    text = ""
    text_base = ""

    if result.sequences:
        text = st.session_state.tokenizer.decode(result.sequences[0].tokens)

    if result_base.sequences:
        text_base = st.session_state.tokenizer.decode(result_base.sequences[0].tokens)

    return text, text_base, time_for_inference

def judge_output(text, text_base):
    resp = anthropic_client.messages.create(
        model="claude-opus-4-5-20251101",
        max_tokens=1000,
        system=JUDGE_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"Text Fine-tuned: {text}, Text Base: {text_base}"}],
    )

    resp = resp.content[0].text.strip().lower()
    return resp

st.title("Personality fine-tuning")

user_message = st.text_area("Ask me anything: ")

if st.button("Send"):
    with st.spinner("Generating response...", show_time=True):
        text, text_base, time_for_inference = query(user_message)

    left, right = st.columns(2)

    st.write(f"Inference time: {time_for_inference}")
    length_of_both_responses = len(text.split()) + len(text_base.split())
    st.write("Words generated: ", length_of_both_responses)

    secs = time_for_inference.total_seconds()
    if secs <= 0:
        secs = 1e-6

    st.write("words/s: ", length_of_both_responses / (2 * secs))

    with left:
        st.write("Fine-tuned result: ", text)

    with right:
        st.write("Base model result: ", text_base)

    with st.spinner("Loading Judge Response"):
        st.write(judge_output(text, text_base))
