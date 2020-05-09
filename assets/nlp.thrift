namespace java nlpservice
namespace py nlpservice

typedef string json 

service NLPService {
        json nlp_encode(1: string text),
        void ping()
}
