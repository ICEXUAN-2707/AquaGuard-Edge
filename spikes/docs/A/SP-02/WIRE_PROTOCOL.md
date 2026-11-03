# SP-02 实验协议 v0.1

prototype_only。MQTT 3.1.1，QoS1，观测retain=false。
Topic为prototype/aquaguard/prototype01/observation；仅受控simulation入口。
线上载荷为候选SensorObservation去除received_at，接收端补UTC时间。
首轮仅允许RECEIVED_FALLBACK/event_time=null。身份为JSON紧凑数组
[device_id,sensor_type,boot_id,seq]的UTF-8 SHA256十六进制值。
seq按传感器、boot递增，重传保持身份和内容。
去重不比较received_at；重复、冲突与乱序为日志分类，不修改原始quality。
硬件入口尚未启用，未确定GPIO、电压、串口参数或驱动协议。
