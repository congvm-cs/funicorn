# curl -X POST http://0.0.0.0:8123/predict_json -d '{img_bytes:@/Users/congvo/Documents/Screen Shot 2020-02-16 at 10.19.57 PM.png}'

curl --header "Content-Type: application/json" \
    -X POST http://0.0.0.0:5005/predict_json -d '{"data":10}'

curl --header "Content-Type: application/json" \
    -X GET http://0.0.0.0:5005/statistics
