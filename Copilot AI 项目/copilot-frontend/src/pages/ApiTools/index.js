import { Table, Button, Modal, Upload,message } from 'antd';
import { DeleteOutlined, EditOutlined } from '@ant-design/icons';
import { useState, useEffect } from 'react';
import { ToolsApi, DeleteAllToolApi, UploadToolApi,DeleteOneToolApi } from '../../api/agent';

import { UploadOutlined } from '@ant-design/icons';

const demoData = [
        {
          "key": "1",
          "index": 1,
          "name": "用户查询API",
          "description": "通过用户ID查询详细信息",
          "params": "123",
          "method": "GET"
        },
        {
          "key": "2",
          "index": 2,
          "name": "订单创建API",
          "description": "创建新的订单记录",
          "params": "123",
          "method": "POST"
        },
         {
          "key": "3",
          "index": 3,
          "name": "订单创建API",
          "description": "创建新的订单记录",
          "params": "123",
          "method": "POST"
        }, {
          "key": "4",
          "index": 4,
          "name": "订单创建API",
          "description": "创建新的订单记录",
          "params": "123",
          "method": "POST"
        }
      ];
export default function ApiTools() {

  const [data, setData] = useState(demoData);
  const [selectedRow, setSelectedRow] = useState(null);

  const delete_all_tool = ()=>{
    DeleteAllToolApi().then(res=>{
      if(res.status === 200){
        handleGetAllData();
        message.success('清空成功');
      }
    }).catch(err=>{
      console.log(err);
      message.error('清空失败');
    })

  }

  const handleGetAllData = () => {
    ToolsApi().then(res => {
      console.log(res)
      if (res.status === 200) {
        setData(res.data.results);
      }
    }).catch(err => {
      console.log(err);
    })
	};

  useEffect(() => {
    handleGetAllData();
  }, []);
  

  // 表格列配置
  const columns = [
    { title: '序号', dataIndex: 'index' },
    { title: 'API名称', dataIndex: 'name' },
    { title: 'API描述', dataIndex: 'description' },
    { title: '请求参数', dataIndex: 'params' },{ title: '请求方法', dataIndex: 'method' },
    { 
      title: '操作',
      render: (_, record) => (
        <>
          <Button danger icon={<DeleteOutlined />} onClick={() => {
            console.log(record)
             
           DeleteOneToolApi({"ids":[record.key]}).then(res=>{
            if(res.status === 200){
              handleGetAllData();
              message.success('删除成功');
            }
           }).catch(err=>{
            console.log(err);
            message.error('删除失败');
           })


          }} />
        </>
      )
    }
  ];

  return (
    <div className="api-tools-page">
      <div className="table-header">
        <h3 className="neon-title"></h3>
        <div className="toolbar-right">
          <Button 
            danger
            className="danger-btn"
            onClick={delete_all_tool}
            style={{ marginRight: 16 }}
          >
            清空所有工具
          </Button>
          <Upload
            name="file"
            customRequest={({ file }) => {
              UploadToolApi(file).then(res => {
                if (res.status === "success") {
                  message.success('上传成功');
                  handleGetAllData();
                }
              }).catch(err => {
                message.error('上传失败：' + err.message);
              });
            }}
            showUploadList={false}
            beforeUpload={file => {
              const isJSON = file.type === 'application/json';
              if (!isJSON) {
                message.error('仅支持JSON格式文件');
              }
              return isJSON;
            }}
          >
            <Button 
              type="primary" 
              className="upload-btn"
              icon={<UploadOutlined />}
            >
              上传所有工具
            </Button>
          </Upload>
        </div>
      </div>
      
      <Table
        columns={columns}
        dataSource={data}
        bordered
        pagination={true}
        className="api-table"
        rowClassName={() => 'table-row'}
      />
    </div>
  );
};
