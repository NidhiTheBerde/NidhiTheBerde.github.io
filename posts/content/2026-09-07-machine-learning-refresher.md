Most of my day to day work right now is LLMs and agents: prompts, tool calls, retries, structured output. It's easy to let "machine learning" quietly narrow down to just that. So this is me going back to the fundamentals for a bit, the stuff that got a little rusty since grad school, written out the way I'd actually explain it to someone rather than the textbook version.

There are three broad ways a model can learn, and almost everything else is a variation on one of these.

## Supervised learning: learning from labeled examples

This is the one most people picture when they hear "machine learning." You have a dataset where every example already comes with the correct answer attached, and the model's job is to learn the pattern that connects the inputs to that answer well enough to predict it on new, unseen examples.

It splits into two flavors depending on what kind of answer you're predicting.

**Regression** is for when the answer is a number on a continuous scale. Predicting a house price from square footage, location, and number of bedrooms. Predicting tomorrow's temperature. Predicting how long a pipeline job will take to run based on input size. The model isn't picking from a fixed set of options, it's estimating a value.

**Classification** is for when the answer is a category. Is this email spam or not. Is this review positive, negative, or neutral. Is this transaction fraudulent. The model learns decision boundaries that separate the classes, and depending on the problem you might be doing binary classification (two options) or multi-class (more than two).

The common thread: you need labeled data, and the quality of your labels puts a hard ceiling on how good the model can get. Garbage labels, garbage model, no matter how good the algorithm is.

## Unsupervised learning: finding structure without labels

Here you don't have answers to learn from. You just have data, and you're asking the model to find whatever structure is actually in it.

**Clustering** groups similar items together without you telling it what the groups should be ahead of time. Customer segmentation is the classic example: you don't start with predefined customer types, you let the algorithm find natural groupings in behavior and spending, and then you go look at what it found and decide if it's useful.

**Anomaly detection** is about spotting the things that don't fit the pattern everything else follows. Fraud detection, equipment failure prediction, catching a weird spike in an API's error rate before anyone files a ticket about it. The model learns what "normal" looks like and flags what deviates from it.

**Association rule learning** finds relationships between items that show up together. The textbook example is market basket analysis: people who buy diapers also tend to buy beer (a real, often-cited retail finding). It's less flashy than the other two, but it's the backbone of a lot of recommendation logic.

## Reinforcement learning: learning by trial and error

This one is a different shape entirely. There's no dataset of labeled examples sitting around beforehand. Instead there's an agent, an environment, and a feedback loop: the agent takes an action, the environment responds, and the agent gets a reward or a penalty based on how good that action turned out to be. Over many, many iterations, it adjusts its behavior to chase higher reward.

The interesting tension inside RL is exploration versus exploitation. Exploitation means doing the thing you already know works well. Exploration means trying something new that might work even better, or might just waste a turn. Lean too hard on exploitation and you get stuck at a decent-but-not-great strategy. Lean too hard on exploration and you never actually cash in on what you've learned. Most of the cleverness in RL algorithms is really about managing that tradeoff well.

This is the paradigm behind game-playing agents, robotics, and a lot of autonomous systems work, and it's also, worth noting, conceptually close to how RLHF fine-tunes the LLMs I work with every day. The reward signal is different (human preference instead of a game score) but the underlying loop of act, get feedback, adjust is the same idea.

## Why bother with the refresher

None of this is new information to me, it's stuff I learned properly the first time around. But there's a real difference between having learned something and being able to reach for it fluently when it's actually relevant. Most of what I build day to day sits on top of a frontier LLM someone else trained, which makes it easy to stop thinking about what's underneath. Going back through the fundamentals every so often is just making sure I still actually own the knowledge, not just the API calls on top of it.
