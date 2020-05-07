../wrk -t 4 -c 128 -d 20s --timeout=10s -s benchmark.lua http://127.0.0.1:5005/predict_img_bytes
