const AppConfig = {
    // apiEndpoint: "/rasp-shutter/api/",

    apiEndpoint: "http://192.168.0.10:5000/rasp-shutter/api/",
};

export default {
    data() {
        return {
            AppConfig: AppConfig,
        };
    },
};
