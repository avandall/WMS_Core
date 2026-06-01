from pathlib import Path

from datasets import load_dataset
from trl import SFTTrainer
from transformers import TrainingArguments
from unsloth import FastLanguageModel

def main():
    script_dir = Path(__file__).resolve().parent
    data_path = script_dir / "data" / "wms_data_fixed.jsonl"
    output_dir = script_dir / "wms_checkpoints"
    final_model_dir = script_dir / "wms_final_model"

    output_dir.mkdir(parents=True, exist_ok=True)

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name="unsloth/Llama-3.2-1B-Instruct-bnb-4bit",
        max_seq_length=1024,
        load_in_4bit=True,
    )

    model = FastLanguageModel.get_peft_model(
        model,
        r=16,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
        lora_alpha=16,
        lora_dropout=0,
        bias="none",
    )

    def formatting_prompts_func(examples):
        instructions = examples["instruction"]
        inputs = examples["input"]
        outputs = examples["output"]
        texts = []
        for instruction, input, output in zip(instructions, inputs, outputs):
            text = f"### Instruction:\n{instruction}\n\n### Input:\n{input}\n\n### Response:\n{output}"
            texts.append(text)
        return {"text": texts}

    dataset = load_dataset("json", data_files=str(data_path), split="train")
    dataset = dataset.map(formatting_prompts_func, batched=True)

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        dataset_text_field="text",
        max_seq_length=1024,
        args=TrainingArguments(
            per_device_train_batch_size=1,
            gradient_accumulation_steps=4,
            warmup_steps=5,
            max_steps=200,
            learning_rate=2e-4,
            fp16=True,
            logging_steps=1,
            optim="adamw_8bit",
            weight_decay=0.01,
            output_dir=str(output_dir),
            save_steps=50,
            save_total_limit=2,
        ),
    )

    trainer.train()

    model.save_pretrained(str(final_model_dir))
    tokenizer.save_pretrained(str(final_model_dir))

if __name__ == "__main__":
    main()
