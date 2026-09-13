import { Table, Button, Modal, Upload } from 'antd';
import { DeleteOutlined, EditOutlined } from '@ant-design/icons';
import { useState } from 'react';

export default function ApiTools() {

  const [data, setData] = useState([]);
  const [selectedRow, setSelectedRow] = useState(null);
  
  // 删除确认弹窗
  const confirmDelete = () => {
    Modal.confirm({
      title: '确认删除该API工具？',
      content: '此操作不可撤销',
      onOk() {
        setData(data.filter(item => item.key !== selectedRow.key));
      }
    });
  };

  // 表格列配置
  const columns = [
    { title: '序号', dataIndex: 'index' },
    { title: 'API名称', dataIndex: 'name' },
    { title: 'API描述', dataIndex: 'description' },
    { 
      title: '操作',
      render: (_, record) => (
        <>
          <Button danger icon={<DeleteOutlined />} onClick={() => {
            setSelectedRow(record);
            confirmDelete();
          }} />
          <Button 
            icon={<EditOutlined />}
            onClick={() => Modal.info({
              title: '编辑API工具',
              content: <Upload beforeUpload={file => {
                // 处理JSON文件逻辑
              }} />
            })}
          />
        </>
      )
    }
  ];

  return (
    <div className="api-tools-page">
      <div className="toolbar">
        <Button danger>清空所有工具</Button>
        <Button type="primary">上传所有工具</Button>
      </div>
      <Table 
        columns={columns}
        dataSource={data}
        bordered
        pagination={false}
      />
    </div>
  );
};