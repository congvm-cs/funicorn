# funicorn-start --funicorn-cls main.NLP_B  --http-port 8002 --rpc-cls main.NLPThriftApi --model-cls main.HandlerB --rpc-port 8112 --num-workers 1

funicorn-start --funicorn-cls main.NLPGateWay  --rpc-cls main.NLPThriftApi --model-cls main.WGHandler --rpc-port 5005 --rpc-port 5006