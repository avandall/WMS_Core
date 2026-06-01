#contract tests
Using CPython 3.12.13 interpreter at: /opt/hostedtoolcache/Python/3.12.13/x64/bin/python3.12
Creating virtual environment at: .venv
   Building wms @ file:///home/runner/work/WMS-Project/WMS-Project
Downloading networkx (2.0MiB)
Downloading kubernetes (1.9MiB)
Downloading nvidia-cufft (204.2MiB)
Downloading nvidia-cuda-cupti (10.2MiB)
Downloading nvidia-cusparselt-cu13 (162.0MiB)
Downloading nvidia-nccl-cu13 (187.4MiB)
Downloading torchao (3.1MiB)
Downloading nvidia-cuda-runtime (2.1MiB)
Downloading faker (1.9MiB)
Downloading xformers (3.1MiB)
Downloading cryptography (4.3MiB)
Downloading sqlalchemy (3.2MiB)
Downloading langchain-community (2.4MiB)
Downloading diffusers (4.8MiB)
Downloading unsloth (59.8MiB)
Downloading nvidia-curand (56.8MiB)
Downloading nvidia-nvjitlink (38.8MiB)
Downloading scipy (33.6MiB)
Downloading faiss-cpu (22.7MiB)
Downloading chromadb (22.1MiB)
Downloading numpy (15.9MiB)
Downloading mypy (14.1MiB)
Downloading pandas (10.4MiB)
Downloading transformers (10.2MiB)
Downloading scikit-learn (8.5MiB)
Downloading tree-sitter-languages (8.0MiB)
Downloading torchvision (7.2MiB)
Downloading pillow (6.8MiB)
Downloading grpcio (6.5MiB)
Downloading cuda-bindings (6.0MiB)
Downloading sympy (6.0MiB)
Downloading zstandard (5.3MiB)
Downloading uvloop (4.2MiB)
Downloading psycopg2-binary (4.1MiB)
Downloading hf-xet (4.0MiB)
Downloading hf-transfer (3.4MiB)
Downloading tokenizers (3.1MiB)
Downloading pydantic-core (2.0MiB)
Downloading black (1.7MiB)
Downloading nvidia-nvshmem-cu13 (57.6MiB)
Downloading onnxruntime (17.2MiB)
Downloading bitsandbytes (57.8MiB)
Downloading torch (506.1MiB)
Downloading nvidia-cublas (403.5MiB)
Downloading nvidia-cusolver (191.6MiB)
Downloading nvidia-cudnn-cu13 (349.1MiB)
Downloading triton (179.5MiB)
Downloading nvidia-cusparse (139.2MiB)
Downloading nvidia-cuda-nvrtc (86.0MiB)
Downloading pyarrow (46.6MiB)
 Downloaded black
Downloading aiohttp (1.7MiB)
 Downloaded kubernetes
 Downloaded networkx
Downloading sentencepiece (1.3MiB)
Downloading pygments (1.2MiB)
 Downloaded pydantic-core
Downloading nvidia-cufile (1.2MiB)
 Downloaded nvidia-cuda-runtime
Downloading openai (1.1MiB)
 Downloaded faker
Downloading tiktoken (1.1MiB)
 Downloaded langchain-community
Downloading setuptools (1.0MiB)
 Downloaded xformers
 Downloaded torchao
 Downloaded pygments
 Downloaded tokenizers
 Downloaded sqlalchemy
 Downloaded nvidia-cufile
 Downloaded sentencepiece
 Downloaded tiktoken
 Downloaded hf-transfer
 Downloaded aiohttp
 Downloaded setuptools
 Downloaded hf-xet
 Downloaded psycopg2-binary
 Downloaded openai
 Downloaded uvloop
 Downloaded cryptography
 Downloaded diffusers
 Downloaded zstandard
 Downloaded cuda-bindings
 Downloaded sympy
 Downloaded grpcio
 Downloaded pillow
 Downloaded torchvision
 Downloaded tree-sitter-languages
 Downloaded scikit-learn
 Downloaded nvidia-cuda-cupti
      Built wms @ file:///home/runner/work/WMS-Project/WMS-Project
 Downloaded numpy
 Downloaded transformers
 Downloaded chromadb
 Downloaded faiss-cpu
 Downloaded onnxruntime
 Downloaded pandas
 Downloaded scipy
 Downloaded nvidia-nvjitlink
 Downloaded mypy
 Downloaded nvidia-curand
 Downloaded nvidia-nvshmem-cu13
 Downloaded bitsandbytes
 Downloaded pyarrow
 Downloaded nvidia-cuda-nvrtc
 Downloaded unsloth
 Downloaded nvidia-cusparse
 Downloaded nvidia-cusparselt-cu13
 Downloaded nvidia-nccl-cu13
 Downloaded nvidia-cusolver
 Downloaded nvidia-cufft
 Downloaded triton
 Downloaded nvidia-cudnn-cu13
 Downloaded nvidia-cublas
 Downloaded torch
Installed 219 packages in 577ms
ImportError while loading conftest '/home/runner/work/WMS-Project/WMS-Project/tests/conftest.py'.
tests/conftest.py:294: in <module>
    from app.modules.products.application.commands import CreateProductCommand, UpdateProductCommand, DeleteProductCommand
E   ModuleNotFoundError: No module named 'app.modules.products.application.commands'
Error: Process completed with exit code 4.

#lint ruff check
Run uv run ruff check --select=F9,F821,F822,F823 .
error: Failed to spawn: `ruff`
  Caused by: No such file or directory (os error 2)
Error: Process completed with exit code 2.


#proto
 Downloaded nvidia-cusolver
 Downloaded nvidia-cufft
 Downloaded nvidia-cudnn-cu13
 Downloaded nvidia-cublas
 Downloaded torch
Installed 219 packages in 1.10s
/home/runner/work/WMS-Project/WMS-Project/.venv/bin/python: Error while finding module specification for 'grpc_tools.protoc' (ModuleNotFoundError: No module named 'grpc_tools')
Traceback (most recent call last):
  File "/home/runner/work/WMS-Project/WMS-Project/scripts/gen_protos.py", line 89, in <module>
    main()
  File "/home/runner/work/WMS-Project/WMS-Project/scripts/gen_protos.py", line 74, in main
    subprocess.check_call(cmd)
  File "/opt/hostedtoolcache/Python/3.12.13/x64/lib/python3.12/subprocess.py", line 413, in check_call
    raise CalledProcessError(retcode, cmd)
subprocess.CalledProcessError: Command '['/home/runner/work/WMS-Project/WMS-Project/.venv/bin/python', '-m', 'grpc_tools.protoc', '-I/home/runner/work/WMS-Project/WMS-Project/proto', '--python_out=/home/runner/work/WMS-Project/WMS-Project/Services/identity-service/src/identity_service/gen-ozzac3h3', '--grpc_python_out=/home/runner/work/WMS-Project/WMS-Project/Services/identity-service/src/identity_service/gen-ozzac3h3', '/home/runner/work/WMS-Project/WMS-Project/proto/wms/identity/v1/identity.proto']' returned non-zero exit status 1.
Error: Process completed with exit code 1.

#docker compose config validation
Run docker compose config --quiet
env file /home/runner/work/WMS-Project/WMS-Project/.env.docker not found: stat /home/runner/work/WMS-Project/WMS-Project/.env.docker: no such file or directory
Error: Process completed with exit code 1.

#dependencies review
Run actions/dependency-review-action@v4
Error: Dependency review is not supported on this repository. Please ensure that Dependency graph is enabled, see https://github.com/avandall/WMS-Project/settings/security_analysis