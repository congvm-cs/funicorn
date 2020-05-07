namespace java funicorn
namespace py funicorn

typedef string json 

service FunicornService {
        json predict_img_bytes(1: binary img_bytes),
        void ping()
}
