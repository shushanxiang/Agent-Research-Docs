import React, { useState,useEffect } from 'react';
import Graph from 'react-graph-vis';
import { Row, Col, Card, Descriptions, Typography } from 'antd';

const { Title, Paragraph } = Typography;

const KnowledgeGraph = ({ nodes, edges }) => {
  // 初始化图数据
  // 初始化图数据
  const init_graphData = {
    nodes: nodes.map((node) => ({
      ...node,
      details: {
        name: node.label,
        type: node.group,
        desc: `这是${node.label}的描述`,
      },
    })),
    edges: edges.map((edge) => ({
      ...edge,
    })),
  };

  // 状态用于存储当前选中的节点信息
  const [selectedNode, setSelectedNode] = useState(null);
  const [graphData, setGraphData] = useState(init_graphData);
  

  // 图的配置选项
  const options = {
    nodes: {
      shape: 'dot',
      size: 20,
      font: {
        size: 14,
        color: '#333',
      },
    },
    edges: {
      width: 2,
      font: {
        size: 12,
        color: '#666',
      },
      color: '#888',
    },
    layout: {
      hierarchical: false,
    },
    physics: {
      enabled: true,
      barnesHut: {
        gravitationalConstant: -1000,
        springConstant: 0.01,
        springLength: 100,
      },
    },
  };

  // 事件处理函数
  const events = {
    select: (event) => {
      const { nodes } = event;
      if (nodes.length > 0) {
        const selectedNodeId = nodes[0];
        const selectedNode = graphData.nodes.find((node) => node.id === selectedNodeId);
        setSelectedNode(selectedNode);
      } else {
        setSelectedNode(null);
      }
    },
  };

  return (
    <Row gutter={24}>
      <Col span={16}>
        <Graph
          graph={graphData}
          options={options}
          events={events}
          style={{ height: '600px', width: '100%' }}
        />
      </Col>
      <Col span={8}>
        <Card
          title="节点详情"
          bordered={false}
          style={{ borderRadius: '8px', boxShadow: '0 4px 8px rgba(0, 0, 0, 0.1)' }}
          headStyle={{ backgroundColor: '#f0f2f5', borderRadius: '8px 8px 0 0' }}
          bodyStyle={{ padding: '20px' }}
        >
          {selectedNode ? (
            <Descriptions column={1} bordered style={{ marginBottom: '20px' }}>
              <Descriptions.Item label="节点名称" contentStyle={{ fontWeight: 'bold' }}>
                {selectedNode.details.name}
              </Descriptions.Item>
              <Descriptions.Item label="类型" contentStyle={{ color: '#52c41a' }}>
                {selectedNode.details.type}
              </Descriptions.Item>
              <Descriptions.Item label="描述">
                <Paragraph>{selectedNode.details.desc}</Paragraph>
              </Descriptions.Item>
            </Descriptions>
          ) : (
            <Paragraph style={{ textAlign: 'center', color: '#999' }}>
              点击知识图谱中的节点以查看详细信息
            </Paragraph>
          )}
        </Card>
      </Col>
    </Row>
  );
};

export default KnowledgeGraph;