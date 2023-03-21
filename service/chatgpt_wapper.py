import random
import time

import openai  # for OpenAI API calls
import traceback
import json
import asyncio
from loguru import logger
from backoff import on_exception, expo
from tools.openai_token_control import discard_overlimit_messages
import concurrent.futures
from errors import Errors

base = {"role": "system", "content": "You are a helpful assistant."}


async def process(prompt, options, memory_count, top_p, message_store, timeout, model="gpt-3.5-turbo"):
    """
    发文字消息
    """
    # 不能是空消息
    if not prompt:
        logger.error("Prompt is empty.")
        yield Errors.PROMPT_IS_EMPTY.value
        return

    # 内容审查
    moderation_params = dict(
        model='text-moderation-stable',
        input=prompt,
    )
    moderation_res = await _moderation_create_async(moderation_params)
    if moderation_res is None:
        yield Errors.SOMETHING_WRONG_IN_OPENAI_MODERATION_API.value
        return

    try:
        if moderation_res.results[0].flagged:
            warning_text = "[This content does not comply with OpenAI's usage policy. : {} ]".format(
                prompt
            )
            logger.warning(warning_text)
            yield Errors.NOT_COMPLY_POLICY.value
            return

        chat = {"role": "user", "content": prompt}

        # 组合历史消息
        if options:
            parent_message_id = options.get("parentMessageId")
            messages = message_store.get_from_key(parent_message_id)
            if messages:
                messages.append(chat)
            else:
                messages = [base, chat]
        else:
            parent_message_id = None
            messages = [base, chat]

        # 记忆
        messages = messages[-memory_count:]

        # 消息不能超过token限制
        # todo 压缩过去消息
        messages = discard_overlimit_messages(messages)

        # send to OpenAI
        params = dict(
            stream=True, messages=messages, model=model, top_p=top_p, timeout=timeout
        )
        if parent_message_id:
            params["request_id"] = parent_message_id

        res = await _chat_completions_create_async(params)
        if res is None:
            yield Errors.SOMETHING_WRONG_IN_OPENAI_GPT_API.value
            return

        # 处理结果
        text = ""
        role = ""
        prev_message_dict = {}
        for openai_object in res:
            openai_object_dict = openai_object.to_dict_recursive()

            prev_message_dict = openai_object_dict

            if not role:
                role = openai_object_dict["choices"][0]["delta"].get("role", "")

            text_delta = openai_object_dict["choices"][0]["delta"].get("content", "")
            text += text_delta

            message = json.dumps(dict(
                role=role,
                id=openai_object_dict["id"],
                parentMessageId=parent_message_id,
                text=text,
                # delta=text_delta,
                # detail=dict(
                #     id=openai_object_dict["id"],
                #     object=openai_object_dict["object"],
                #     # created=openai_object_dict["created"],
                #     # model=openai_object_dict["model"],
                #     # choices=openai_object_dict["choices"]
                # )
            ))
            yield "data: " + message

    except:
        err = traceback.format_exc()
        logger.error(err)
        yield Errors.SOMETHING_WRONG.value
        return

    try:
        # save to cache
        chat = {"role": role, "content": text}
        messages.append(chat)

        parent_message_id = prev_message_dict["id"]
        message_store.set(parent_message_id, messages)
    except:
        err = traceback.format_exc()
        logger.error(err)


@on_exception(expo, openai.error.RateLimitError, max_tries=5)
def _moderation_create(params):
    return openai.Moderation.create(**params)


async def _moderation_create_async(params):
    with concurrent.futures.ThreadPoolExecutor() as executor:
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                executor, _moderation_create, params
            )
        except:
            err = traceback.format_exc()
            logger.error(err)
            # 这里处理 openai.error.RateLimitError 之外的错误
            return None
    return result


@on_exception(expo, openai.error.RateLimitError, max_tries=5)
def _chat_completions_create(params):
    return openai.ChatCompletion.create(**params)


async def _chat_completions_create_async(params):
    with concurrent.futures.ThreadPoolExecutor() as executor:
        try:
            result = await asyncio.get_event_loop().run_in_executor(
                executor, _chat_completions_create, params
            )
        except:
            err = traceback.format_exc()
            logger.error(err)
            # 这里处理 openai.error.RateLimitError 之外的错误
            return None
    return result
