from sentence_transformers import SentenceTransformer, InputExample, losses, evaluation
from torch.utils.data import DataLoader
import pandas as pd

# 1. 准备训练数据
# 假设你有一个包含句子对的 CSV 文件，其中第一列为句子1，第二列为句子2，第三列为相似度标签（0或1）
train_df = pd.read_csv("train_data.csv")
train_examples = [
    InputExample(texts=[row["sentence1"], row["sentence2"]], label=row["label"])
    for _, row in train_df.iterrows()
]

# 2. 加载预训练的 BGE 模型
model = SentenceTransformer("BAAI/bge-large-zh-v1.5")  # 中文模型[^2^]

# 3. 定义训练参数
train_loss = losses.CosineSimilarityLoss(model=model)
train_dataloader = DataLoader(train_examples, shuffle=True, batch_size=16)
num_epochs = 3

# 4. 定义评估器（可选）
# 假设你有一个验证集，用于评估模型性能
evaluator = evaluation.EmbeddingSimilarityEvaluator.from_input_examples(
    train_examples[:100], name="validation"
)

# 5. 训练模型
model.fit(
    train_objectives=[(train_dataloader, train_loss)],
    epochs=num_epochs,
    evaluator=evaluator,
    evaluation_steps=1000,
    save_best_model=True,
    show_progress_bar=True,
)

# 6. 保存模型
model.save("output/bge_model")