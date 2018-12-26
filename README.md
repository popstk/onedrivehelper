# onedrivehelper
onedrive helper


## 备忘
#### aria2下载完成
<https://stackoverflow.com/questions/9150187/cant-get-on-download-complete-to-work-with-aria2>

- `on-bt-download-complete`
- `on-download-complete`

#### onedrive api
- [上传大文件](https://docs.microsoft.com/zh-cn/onedrive/developer/sp2019/docs/rest-api/api/driveitem_createuploadsession?view=odsp-graph-online)

## 坑
#### 400 Annotations must be specified before other elements in a JSON object
request body:
``` json
{
    "item": {
        "name": "xxx",
        "@name.conflictBehavior": "rename"
    }
}
```

status_code = 400, respond body:
``` json
{
    "error": {
        "code": "invalidRequest",
        "message": "Annotations must be specified before other elements in a JSON object"
    }
}
```
注意序列化时，需要把item group带@的key放前面，即：
``` json
{
    "item": {
        "@name.conflictBehavior": "rename",
        "name": "xxx"
    }
}
```
python的json.dumps默认是unorder的，需要传入参数`sort_keys`

<https://stackoverflow.com/questions/10844064/items-in-json-object-are-out-of-order-using-json-dumps>

