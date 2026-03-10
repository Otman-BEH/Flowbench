idf_component_register(SRCS "main.cpp" "Wifi.cpp"
                    INCLUDE_DIRS "."
        REQUIRES nvs_flash esp_wifi esp_netif esp_event esp_http_server driver)
