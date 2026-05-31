from unsloth import FastLanguageModel
import torch
from datasets import load_dataset
from trl import SFTTrainer
from transformers import TrainingArguments

def main():
    # --- 1. CẤU HÌNH ĐƯỜNG DẪN ---
    import os
    # Get absolute path to script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    DATA_PATH = os.path.join(script_dir, "wms_data.jsonl") # Path tới file dữ liệu của bạn
    OUTPUT_DIR = os.path.join(script_dir, "wms_checkpoints")

    # --- 2. LOAD MODEL (Tối ưu cho Laptop 6GB VRAM) ---
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name = "unsloth/Llama-3.2-1B-Instruct-bnb-4bit",
        max_seq_length = 1024,
        load_in_4bit = True,
    )

    # Thêm LoRA Adapter (Kẹp giấy ghi chú)
    model = FastLanguageModel.get_peft_model(
        model,
        r = 16,
        target_modules = ["q_proj", "k_proj", "v_proj", "o_proj"],
        lora_alpha = 16,
        lora_dropout = 0,
        bias = "none",
    )

    # --- 3. XỬ LÝ DATASET ---
    # Load file jsonl và định dạng lại cho đúng chuẩn Unsloth
    def formatting_prompts_func(examples):
        instructions = examples["instruction"]
        inputs       = examples["input"]
        outputs      = examples["output"]
        texts = []
        for instruction, input, output in zip(instructions, inputs, outputs):
            # Format này giúp AI nhận diện rõ Instruction/Input/Output
            text = f"### Instruction:\n{instruction}\n\n### Input:\n{input}\n\n### Response:\n{output}"
            texts.append(text)
        return { "text" : texts, }

    dataset = load_dataset("json", data_files=DATA_PATH, split="train")
    dataset = dataset.map(formatting_prompts_func, batched = True)

    # --- 4. THIẾT LẬP TRAINING ---
    trainer = SFTTrainer(
        model = model,
        tokenizer = tokenizer,
        train_dataset = dataset,
        dataset_text_field = "text",
        max_seq_length = 1024,
        args = TrainingArguments(
            per_device_train_batch_size = 1,
            gradient_accumulation_steps = 4,
            warmup_steps = 5,
            max_steps = 200, # Tổng số bước train
            learning_rate = 2e-4,
            fp16 = True,
            logging_steps = 1,
            optim = "adamw_8bit", # Dùng bản 8-bit để tiết kiệm VRAM
            weight_decay = 0.01,
            output_dir = OUTPUT_DIR,
            save_steps = 50,      # Lưu sau mỗi 50 bước
            save_total_limit = 2,
        ),
    )

    # --- 5. BẮT ĐẦU TRAIN ---
    # Nếu muốn chạy tiếp từ bản lưu cũ, đổi thành: trainer.train(resume_from_checkpoint = True)
    trainer.train()

    # --- 6. LƯU MODEL CUỐI CÙNG ---
    model.save_pretrained("wms_final_model")
    tokenizer.save_pretrained("wms_final_model")

if __name__ == "__main__":
    main()