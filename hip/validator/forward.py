# The MIT License (MIT)
# Copyright © 2023 Yuma Rao
# TODO(developer): Set your name
# Copyright © 2023 <your name>

# Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
# documentation files (the “Software”), to deal in the Software without restriction, including without limitation
# the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all copies or substantial portions of
# the Software.

# THE SOFTWARE IS PROVIDED “AS IS”, WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
# THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL
# THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION
# OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
# DEALINGS IN THE SOFTWARE.

import random
import bittensor as bt
from tabulate import tabulate

from hip.protocol import TaskSynapse
from hip.validator.image_generator import generate_image_task
from hip.validator.reward import get_rewards
from hip.utils.uids import get_random_uids
from hip.validator.hip_service import get_llm_task
from hip.validator.captcha_generator import generate_capcha
import time


async def forward(self):
    """
    The forward function is called by the validator every time step. In our case it is called every 10 seconds.

    It is responsible for querying the network and scoring the responses.

    Args:
        self (:obj:`bittensor.neuron.Neuron`): The neuron object which contains all the necessary state for the validator.
    """
    firstTime = False
    # task_gen_step is the wait time between creating and sending tasks.
    task_gen_step = self.config.neuron.task_gen_step

    # Store the last run time
    if not hasattr(self, "_last_run_time"):
        firstTime = True
        self._last_run_time = time.time()

    # Check if task_gen_step seconds have passed
    if time.time() - self._last_run_time < task_gen_step and not firstTime:
        return
    self._last_run_time = time.time()

    bt.logging.debug("Forwarding task to miners")
    miner_uids = get_random_uids(self, k=self.config.neuron.sample_size)
    captcha = generate_capcha()

    # Decide if image or llm task should be sent
    task_type = random.choice(["image", "llm"])
    if task_type == "image":
        task = generate_image_task(captcha=captcha["image"])
    else:
        task = get_llm_task(captcha=captcha["image"])

    bt.logging.debug(f"Task: {task.id} - Generated task type: {task_type}")
    ground_truth = task.answer
    task.answer = ""
    task_to_print = task.to_dict()
    # replace image and captcha entries with true or false
    task_to_print["image"] = (
        "True" if task_to_print["image"] and task_to_print["image"] != "" else "False"
    )
    task_to_print["captcha"] = (
        "True"
        if task_to_print["captcha"] and task_to_print["captcha"] != ""
        else "False"
    )
    bt.logging.debug(
        f"Task: {task.id} - Generated task: {task_to_print}",
    )
    bt.logging.debug(f"Task: {task.id} - Ground truth: {ground_truth}")
    bt.logging.debug(f"Task: {task.id} - Captcha: {captcha['text']}")

    bt.logging.debug(
        f"Task: {task.id} - Sending task to miners with timeout {self.config.neuron.timeout}"
    )
    bt.logging.debug(f"Task: {task.id} - Chosen Miner IDs: {miner_uids}")
    # The dendrite client queries the network.
    responses = await self.dendrite(
        # Send the query to selected miner axons in the network.
        axons=[self.metagraph.axons[uid] for uid in miner_uids],
        synapse=task,
        timeout=self.config.neuron.timeout,
        # All responses have the deserialize function called on them before returning.
        # You are encouraged to define your own deserialization function.
        deserialize=True,
    )
    task.answer = ground_truth

    # Log the results for monitoring purposes.
    # bt.logging.info(f"Received responses: {responses}")
    # For each response print the response's id and the response's answer.
    # TODO(developer): Define how the validator scores responses.
    # Adjust the scores based on responses from miners.
    rewards = get_rewards(
        self, task=task, responses=responses, captcha_ground_truth=captcha["text"]
    )
    printRecords = []
    for i in range(len(responses)):
        printRecords.append(
            [
                miner_uids[i],  # Miner UID
                responses[i].axon.hotkey,  # Miner Hotkey
                f"{responses[i].axon.ip}:{responses[i].axon.port}",  # Miner IP:Port
                responses[i].dendrite.status_code,  # Status Code of the response
                # Does the captcha match the ground truth
                responses[i].captchaValue == captcha["text"],
                responses[i].answer
                == ground_truth,  # Does the response match the ground truth
                responses[i].answer[:30],  # Selected Option (First 30 characters)
                rewards[i],  # Reward
            ]
        )

    print(
        tabulate(
            printRecords,
            headers=[
                "UID",
                "Hotkey",
                "IP:Port",
                "Status",
                "Captcha Match",
                "Answer Match",
                "Captcha Text",
                "Selected Answer",
                "Reward n/1",
            ],
        )
    )
    # Update the scores based on the rewards. You may want to define your own update_scores function for custom behavior.
    self.update_scores(rewards, miner_uids)
