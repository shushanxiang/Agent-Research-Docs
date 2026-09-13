import {
  FormOutlined,
  OpenAIFilled,
  UserOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import ReactEcharts from 'echarts-for-react';
import { Switch, Typography, InputNumber } from 'antd';


import {
  Bubble,
  Prompts,
  Sender,
  Suggestion,
  Welcome,
} from '@ant-design/x';
import { Button, Space, Spin } from 'antd';
import { createStyles } from 'antd-style';
import React, { useEffect, useRef, useState } from 'react';
import { ApiPlanningApi, TestTaskStatusApi } from '../../api/agent';
// const { Title, Paragraph } = Typography;

// const nodes = [
//     { name: 'node1',id: 'node1', label: '节点1', group: 1 },
//     { name: 'node2',id: 'node2', label: '节点2', group: 2 },
    
//   ];

//   const edges = [
//    { source: 'node1', target: 'node2', value: '关系1',symbolSize: [5, 20],label: {
//             show: false
//           }, },
//   ];
const fooAvatar = {
  color: '#f56a00',
  backgroundColor: '#fde3cf',
};
const barAvatar = {
  color: '#fff',
  backgroundColor: '#87d068',
};

// var __awaiter =
//   (this && this.__awaiter) ||
//   function (thisArg, _arguments, P, generator) {
//     function adopt(value) {
//       return value instanceof P
//         ? value
//         : new P(function (resolve) {
//             resolve(value);
//           });
//     }
//     return new (P || (P = Promise))(function (resolve, reject) {
//       function fulfilled(value) {
//         try {
//           step(generator.next(value));
//         } catch (e) {
//           reject(e);
//         }
//       }
//       function rejected(value) {
//         try {
//           step(generator['throw'](value));
//         } catch (e) {
//           reject(e);
//         }
//       }
//       function step(result) {
//         result.done ? resolve(result.value) : adopt(result.value).then(fulfilled, rejected);
//       }
//       step((generator = generator.apply(thisArg, _arguments || [])).next());
//     });
//   };
const MOCK_SESSION_LIST = [
  {
    key: '5',
    label: '我想知道苹果产品的库存信息',
    group: 'Today',
  },
  {
    key: '4',
    label: '查询ID为1的物流供应商信息',
    group: 'Today',
  },
  {
    key: '3',
    label: '查询名为京东的物流供应商信息',
    group: 'Today',
  },
  {
    key: '2',
    label: '查询订单ID为1的订单信息',
    group: 'Yesterday',
  },
  {
    key: '1',
    label: '查询产品ID为1的订单信息',
    group: 'Yesterday',
  },
];
const MOCK_SUGGESTIONS = [
  { label: 'Write a report', value: 'report' },
  { label: 'Draw a picture', value: 'draw' },
  {
    label: 'Check some knowledge',
    value: 'knowledge',
    icon: <OpenAIFilled />,
    children: [
      { label: 'About React', value: 'react' },
      { label: 'About Ant Design', value: 'antd' },
    ],
  },
];
const MOCK_QUESTIONS = [
  '查询苹果的产品信息',
  '查询名为京东的物流供应商信息',
];
const AGENT_PLACEHOLDER = 'Generating content, please wait...';
const useCopilotStyle = createStyles(({ token, css }) => {
  return {
    copilotChat: css`
      display: flex;
      flex-direction: column;
      background: ${token.colorBgContainer};
      color: ${token.colorText};
    `,
    // chatHeader 样式
    chatHeader: css`
      height: 52px;
      box-sizing: border-box;
      border-bottom: 1px solid ${token.colorBorder};
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 10px 0 16px;
    `,
    headerTitle: css`
      font-weight: 600;
      font-size: 15px;
    `,
    headerButton: css`
      font-size: 18px;
    `,
    conversations: css`
      width: 300px;
      .ant-conversations-list {
        padding-inline-start: 0;
      }
    `,
    // chatList 样式
    chatList: css`
      overflow: auto;
      padding-block: 16px;
      flex: 1;
    `,
    chatWelcome: css`
      margin-inline: 16px;
      padding: 12px 16px;
      border-radius: 2px 12px 12px 12px;
      background: ${token.colorBgTextHover};
      margin-bottom: 16px;
    `,
    loadingMessage: css`
      background-image: linear-gradient(90deg, #ff6b23 0%, #af3cb8 31%, #53b6ff 89%);
      background-size: 100% 2px;
      background-repeat: no-repeat;
      background-position: bottom;
    `,
    confirmationMessage: css`
      border: 2px solid ${token.colorPrimary};
      border-radius: 8px;
      background-color: ${token.colorPrimaryBg};
      padding: 12px;
    `,
    // chatSend 样式
    chatSend: css`
      padding: 12px;
    `,
    sendAction: css`
      display: flex;
      align-items: center;
      margin-bottom: 12px;
      gap: 8px;
    `,
    speechButton: css`
      font-size: 18px;
      color: ${token.colorText} !important;
    `,
  };
});
const Copilot = props => {
  const { nodes, edges, setNodes, setEdges, copilotOpen, setCopilotOpen, isCopilot, isNotContext, setIsCopilot, setIsNotContext,contextNumber,setContextNumber,title,setTitle,taskId,setTaskId,taskStatus,setTaskStatus } = props;



  const { styles } = useCopilotStyle();
  const attachmentsRef = useRef(null);
  const abortController = useRef(null);

  // ==================== State ====================
  const [messageHistory, setMessageHistory] = useState({});
  const [sessionList, setSessionList] = useState(MOCK_SESSION_LIST);
  const [curSession, setCurSession] = useState(sessionList[0].key);
  const [contextOpen, setContextOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [inputValue, setInputValue] = useState('');
  /**
   * 🔔 Please replace the BASE_URL, PATH, MODEL, API_KEY with your own values.
   */
  // ==================== Runtime ====================
  
  
  const [messages, setMessages ] = useState([]);
  // ==================== Event ====================
  // 新增状态跟踪流式请求
  const [streamInterval, setStreamInterval] = useState(null);
  const [taskInterval, setTaskInterval] = useState(null);
  
  const testUserSubmit = (systemOutput,nodes,edges,title) => {
    const newMessage = {
      id: Date.now(),
      message: { content: '', role: 'assistant' },
      status: 'streaming'
    };
    setMessages(prev => [...prev, newMessage]);
  
    let accumulated = '';
    const processChunk = (chunk) => {
      accumulated += chunk;
      setMessages(prev => prev.map(msg => 
        msg.id === newMessage.id 
          ? {...msg, message: { ...msg.message, content: accumulated }}
          : msg
      ));
    };
    let index = 0;
    const interval = setInterval(() => {
      if (index < systemOutput.length) {
        processChunk(systemOutput[index]);
        index++;
      } else {
        clearInterval(interval);
        setMessages(prev => prev.map(msg =>
          msg.id === newMessage.id
            ? {...msg, status: 'results'}
            : msg
        ));
        setLoading(false);
        setNodes(nodes)
        setEdges(edges)
        setTitle(title)
      }
    }, 50);
    setStreamInterval(interval);
    return () => clearInterval(interval);
  };
  

  // const testTaskStatus = (task_id) => {
  //   var targetStatus = 0
  //   const interval = setInterval(() => {
  //     TestTaskStatusApi({task_id:task_id}).then(res => {
  //       if (res.status === 200) {
  //         console.log(res.data.task)
  //         if (res.data.task.status !== -1) {
  //           console.log(res.data.task.status,targetStatus)
  //           if(res.data.task.status !== targetStatus){
  //             setTaskStatus(res.data.task.status)
  //             console.log(targetStatus)
  //             targetStatus = res.data.task.status
  //             setNodes(res.data.task.nodes)
  //             setEdges(res.data.task.edges)
  //             setTitle(res.data.task.isSuccess)
  //             console.log("Hello World!")
  //           }
  //         }
  //         else{
  //           console.log("hello world!")
  //            clearInterval(interval);
  //            testUserSubmit(res.data.task.systemOutput,res.data.task.nodes,res.data.task.edges,res.data.task.isSuccess)
  //           setTaskStatus(-1)
  //         }
  //       }
  //     })  
  //   }, 500);
  //   setTaskInterval(interval);
  //   return () => clearInterval(interval);
  // };

  // const handleUserSubmitV2 = val => {
  //   console.log(val)
  //   if (!val || loading) return;
  //   setLoading(true);
  //   setEdges([]);
  //   setNodes([]);
  //   setTitle("");
  //   // messages.push({
  //   //   "id": messages.length+1,
  //   //   "message":{"content":val,"role":"user"},
  //   //   "status": "local"
  //   // })
  //   const userMessage = {
  //     "id": Date.now(), // 使用时间戳或唯一ID生成器更可靠
  //     "message":{"content":val,"role":"user"},
  //     "status": "local"
  //   };
  //   setMessages(prevMessages => [...prevMessages, userMessage]);
  //   var contexts = []
  //   for(let i = 0; i < messages.length; i++){
  //     contexts.push(messages[i].message)
  //   }


  //   var data = {
  //     "query": val,
  //     "contexts":contexts,
  //     "isCopilot": isCopilot,
  //     "isContext": !isNotContext,
  //     "contextNumber": contextNumber
  //   }
  //   console.log(data)
  //   // ApiPlanningApi(data).then(res => {
  //   //   if (res.status === 200) {
  //   //     console.log(res.data)
  //   //     var task_id = res.data.task_id
  //   //     testTaskStatus(task_id)
        
  //   //   }
  //   //   else{
  //   //     setEdges([]);
  //   //     setNodes([]);
  //   //     setTitle("")
  //   //     }
  //   // }).catch(err => {
  //   //   console.log(err);
  //   //   messages.push({
  //   //   "id": messages.length+2,
  //   //   "message":{"content":"System: Error","role":"assistant"},
  //   //   "status": "results"
  //   // })
  //   // setNodes([])
  //   // setEdges([])
  //   // setTitle("")
  //   // setLoading(false)
  //   // }).finally(() => {})
  //     ApiPlanningApi(data).then(res => {
  //     if (res.status === 200 && res.data.task_id) {
  //       // 🚀 不再直接调用轮询函数，而是更新 taskId
  //       // useEffect 会自动捕捉到这个变化并开始轮询
  //       setTaskId(res.data.task_id);
  //     } else {
  //       throw new Error("Failed to get task_id");
  //     }
  //   }).catch(err => {
  //     console.error("API planning error:", err);
  //     const errorMessage = {
  //       id: Date.now(),
  //       message: { content: "System: Error", role: "assistant" },
  //       status: "results"
  //     };
  //     setMessages(prev => [...prev, errorMessage]);
  //     setNodes([]);
  //     setEdges([]);
  //     setTitle("");
  //     setLoading(false);
  //   });



  // };
const handleUserSubmitV2 = val => {
    if (!val || loading) return;

    console.log('1. [Submit] handleUserSubmitV2 triggered with value:', val);

    // 如果当前有待确认状态，发送新消息时自动重置
    if (userConfirmationNeeded) {
      console.log('Resetting user confirmation state as new message is being sent');
      setUserConfirmationNeeded(false);
      setConfirmationMessage('');
      // 从chatList中移除确认消息
      setMessages(prev => prev.filter(msg => msg.status !== 'confirmation'));
    }

    setLoading(true);
    setEdges([]);
    setNodes([]);
    setTitle("");

    const userMessage = {
      id: Date.now(),
      message: { content: val, role: "user" },
      status: "local"
    };
    setMessages(prevMessages => [...prevMessages, userMessage]);

    // 注意：这里的 contexts 应该是包含了当前发送的这条消息
    const contexts = [...messages, userMessage].map(m => m.message);

    const data = {
      query: val,
      contexts,
      isCopilot: isCopilot,
      isContext: !isNotContext,
      contextNumber: contextNumber,
      taskId: taskId
    };

    console.log('2. [Submit] Sending data to ApiPlanningApi:', data);

    ApiPlanningApi(data).then(res => {
      console.log('3. [Submit] ApiPlanningApi SUCCESS! Response:', res);
      if (res.status === 200 && res.data && res.data.task_id) {
        console.log('4. [Submit] Received task_id:', res.data.task_id, '. Updating state...');
        // 🚀 更新 taskId，触发 useEffect
        setTaskId(res.data.task_id);
      } else {
        console.error('5. [Submit] ERROR: Response is OK, but task_id is missing.', res.data);
        setLoading(false); // 出错了也要停止加载状态
      }
    }).catch(err => {
      console.error('5. [Submit] FATAL: ApiPlanningApi request failed!', err);
      const errorMessage = {
        id: Date.now(),
        message: { content: "System: Error on API planning", role: "assistant" },
        status: "results"
      };
      setMessages(prev => [...prev, errorMessage]);
      setNodes([]);
      setEdges([]);
      setTitle("");
      setLoading(false);
    });
  };

  // const handleUserSubmit = val => {
  //   console.log(val)
  //   setLoading(true)
  //   setEdges([]);
  //   setNodes([]);
  //   setTitle("")
  //   messages.push({
  //     "id": messages.length+1,
  //     "message":{"content":val,"role":"user"},
  //     "status": "local"
  //   })
  //   var contexts = []
  //   for(let i = 0; i < messages.length; i++){
  //     contexts.push(messages[i].message)
  //   }


  //   var data = {
  //     "query": val,
  //     "contexts":contexts,
  //     "isCopilot": isCopilot,
  //     "isContext": !isNotContext,
  //     "contextNumber": contextNumber
  //   }
  //   console.log(data)
  //   ApiPlanningApi(data).then(res => {
      
  //     if (res.status === 200) {
  //       console.log(res.data)
  //       testUserSubmit(res.data.systemOutput,res.data.nodes,res.data.edges,res.data.isSuccess)
  //   if(!isCopilot){
  //     setNodes(res.data.nodes)
  //     setEdges(res.data.edges)}
  //     setTitle(res.data.isSuccess)
  //   }
  //   else{
  //     setEdges([]);
  //     setNodes([]);
  //     setTitle("")
  //     }
  //   }).catch(err => {
  //     console.log(err);
  //     messages.push({
  //     "id": messages.length+2,
  //     "message":{"content":"System: Error","role":"assistant"},
  //     "status": "results"
  //   })
  //   setNodes([])
  //   setEdges([])
  //   setTitle("")
  //   setLoading(false)
  //   }).finally(() => {})



  // };

  const onChangeCopilot = (checked) => {
    setIsCopilot(checked)
  };
  const onChangeContext = (checked) => {
    setIsNotContext(checked)
  };

  const onChangeNuber = value => {
  setContextNumber(value)
};
const reload = ()=>{
  setMessages([])
  setNodes([])
  setEdges([])
}

  // ==================== Nodes ====================
  const chatHeader = (
    <div className={styles.chatHeader}>
      <div className={styles.headerTitle}>✨ AI Copilot</div>
      <Space size={0}>
        <Button type="text" icon={<ReloadOutlined />} className={styles.headerButton} onClick={reload} />
      </Space>
    </div>
  );
  const ChatList = () => (
    <div className={styles.chatList}>
      {(messages === null || messages === void 0 ? void 0 : messages.length) ? (
        /** 消息列表 */
        <Bubble.List
          style={{ height: '100%', paddingInline: 16 }}
          items={
            messages === null || messages === void 0
              ? void 0
              : messages.map(i => {
                  // 特殊处理确认消息
                  if (i.status === 'confirmation') {
                    return Object.assign(Object.assign({}, i.message), {
                      classNames: {
                        content: styles.confirmationMessage,
                      }
                      // 移除了确认按钮，用户将通过发送新消息来确认
                    });
                  }
                  return Object.assign(Object.assign({}, i.message), {
                    classNames: {
                      content: i.status === 'loading' ? styles.loadingMessage : '',
                    },
                    typing:
                      i.status === 'loading' ? { step: 5, interval: 20, suffix: <>💗</> } : false,
                  });
                })
          }
          roles={{
            assistant: {
              placement: 'start',
              avatar: { icon: <UserOutlined />, style: barAvatar },
              loadingRender: () => (
                <Space>
                  <Spin size="small" />
                  {AGENT_PLACEHOLDER}
                </Space>
              ),
            },
            user: { placement: 'end',avatar: { icon: <UserOutlined />, style: fooAvatar }, },
            
          }}
        />
      ) : (
        /** 没有消息时的 welcome */
        <>
          <Welcome
            variant="borderless"
            title="👋 欢迎使用Copilot智能操作平台"
            description="请在下方输入框中写入你的请求"
            className={styles.chatWelcome}
          />

          <Prompts
            vertical
            title="I can help："
            items={MOCK_QUESTIONS.map(i => ({ key: i, description: i }))}
            onItemClick={info => {
              var _a;
              return handleUserSubmitV2(
                (_a = info === null || info === void 0 ? void 0 : info.data) === null ||
                  _a === void 0
                  ? void 0
                  : _a.description,
              );
            }}
            style={{
              marginInline: 16,
            }}
            styles={{
              title: { fontSize: 14 },
            }}
          />
        </>
      )}
    </div>
  );
  const chatSender = (
    <div className={styles.chatSend}>

      

      <Switch  checkedChildren="单句模式" unCheckedChildren="上下文模式" onChange={onChangeContext} defaultChecked={isNotContext} style={{marginBottom: 5,marginLeft:10}}/>

    {!isNotContext&&<InputNumber min={1} max={100} defaultValue={1} onChange={onChangeNuber} style={{marginBottom: 5,marginLeft:10}}/>}


      <Suggestion items={MOCK_SUGGESTIONS} onSelect={itemVal => setInputValue(`[${itemVal}]:`)}>
        {({ onTrigger, onKeyDown }) => (
          <Sender
            loading={loading}
            value={inputValue}
            onChange={v => {
              onTrigger(v === '/');
              setInputValue(v);
            }}
            onSubmit={() => {
              console.log(inputValue);
              handleUserSubmitV2(inputValue);
              setInputValue('');
            }}
            onCancel={() => {
              var _a;
              (_a = abortController.current) === null || _a === void 0 ? void 0 : _a.abort();
            }}
            placeholder="Ask or input / use skills"
            onKeyDown={onKeyDown}
            prefix={
              <div>
                <Switch checkedChildren="copilot模式" unCheckedChildren="chat模式" onChange={onChangeCopilot} defaultChecked />

              </div>
            }
            actions={(_, info) => {
              const { SendButton, LoadingButton } = info.components;
              return (
                <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                  {loading ? <LoadingButton onClick={() => {
            clearInterval(taskInterval);
            clearInterval(streamInterval);
            setLoading(false);
            setMessages(prev => prev.map(msg =>
              msg.status === 'streaming' 
                ? {...msg, status: 'interrupted'}
                : msg
            ));
          }}type="default" /> : <SendButton type="primary" />}
                </div>
              );
            }}
          />
        )}
      </Suggestion>
    </div>
  );
  
  // 添加用户确认状态的状态变量
  const [userConfirmationNeeded, setUserConfirmationNeeded] = useState(false);
  const [confirmationMessage, setConfirmationMessage] = useState('');

  // 处理用户确认的函数
  const handleUserConfirmation = () => {
    console.log('User confirmed. Resuming task polling.');
    // 发送确认请求到后端（如果需要）
    // TestTaskConfirmApi({ task_id: taskId }).then(res => {
    //   if (res.status === 200) {
    //     console.log('Confirmation sent to backend successfully.');
    //   }
    // }).catch(err => {
    //   console.error('Failed to send confirmation to backend:', err);
    // });
    
    // 重置用户确认状态，恢复轮询
    setUserConfirmationNeeded(false);
    setConfirmationMessage('');
    // 从chatList中移除确认消息（可选）
    setMessages(prev => prev.filter(msg => msg.status !== 'confirmation'));
  };

  // useEffect(() => {
  //   // history mock
  //   if (messages === null || messages === void 0 ? void 0 : messages.length) {
  //     setMessageHistory(prev => Object.assign(Object.assign({}, prev), { [curSession]: messages }));
  //   }
  // }, [messages]);

  useEffect(() => {
    console.log('A. [Effect] useEffect is running. Current taskId:', taskId, ' | Current loading state:', loading);

    // 当没有 taskId 或正在提交第一个请求时，直接退出
    if (!taskId) {
      console.log('B. [Effect] No taskId, exiting effect.');
      return;
    }
    
    // 如果 taskId 存在，说明可以开始轮询了
    console.log('C. [Effect] taskId found! Setting up polling interval...');
    let targetStatus = 0;
    const intervalId = setInterval(() => {
      // 如果正在等待用户确认，则暂停轮询
      if (userConfirmationNeeded) {
        console.log('D. [Polling] Waiting for user confirmation, skipping poll.');
        return;
      }
      
      console.log(`D. [Polling] Polling for taskId: ${taskId}`);
      TestTaskStatusApi({ task_id: taskId }).then(res => {
        console.log('E. [Polling] Received status response:', res.data);
        if (res.status === 200 && res.data.task) {
          const task = res.data.task;
          
          // 特殊处理：当task.status等于100时，需要用户确认
          if (task.status === 100) {
            console.log('F. [Polling] User confirmation needed. Status:', task.status);
            // 更新chatList显示需确认的信息
            const confirmationMsg = {
              id: Date.now(),
              message: { 
                content: task.systemOutput || '请确认以下信息：\n' + JSON.stringify(task, null, 2), 
                role: 'assistant' 
              },
              status: 'confirmation'
            };
            setMessages(prev => [...prev, confirmationMsg]);
            // 设置用户确认状态，暂停轮询
            setUserConfirmationNeeded(true);
            setConfirmationMessage(task.systemOutput || '请确认以下信息');
            // 更新任务状态
            setTaskStatus(task.status);
            setNodes(task.nodes);
            setEdges(task.edges);
            setTitle(task.isSuccess);
            return;
          }
          
          if (task.status !== -1) {
            console.log('F. [Polling] Task is still running. Status:', task.status);
            // ... (更新中间状态的代码)
            if (task.status !== targetStatus) {
              targetStatus = task.status;
              setTaskStatus(task.status);
              setNodes(task.nodes);
              setEdges(task.edges);
              setTitle(task.isSuccess);
              testUserSubmit(task.systemOutput, task.nodes, task.edges, task.isSuccess);
            }
          } else {
            console.log('G. [Polling] SUCCESS: Task finished! Stopping poll and showing results.');
            clearInterval(intervalId);
            setTaskId(''); // 清空taskId
            testUserSubmit(task.systemOutput, task.nodes, task.edges, task.isSuccess);
            setTaskStatus(-1);
          }
        }
      }).catch(err => {
        console.error('H. [Polling] FATAL: Polling API request failed!', err);
        clearInterval(intervalId);
        setTaskId('');
        setLoading(false);
      });
    }, 1500); // 轮询间隔调整为0.5秒，方便观察

    return () => {
      console.log('I. [Effect Cleanup] Cleaning up interval for taskId:', taskId);
      clearInterval(intervalId);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [taskId, userConfirmationNeeded]); // 添加userConfirmationNeeded作为依赖项
  return (
    <div className={styles.copilotChat} style={{ width: copilotOpen ? 600 : 0 }}>
      {/** 对话区 - header */}
      {chatHeader}

      {/** 对话区 - 消息列表 */}
      <ChatList />

      {/** 对话区 - 输入框 */}
      {chatSender}
    </div>
  );
};
const useWorkareaStyle = createStyles(({ token, css }) => {
  return {
    copilotWrapper: css`
      min-width: 1000px;
      height: 100vh;
      display: flex;
    `,
    workarea: css`
      flex: 1;
      background: ${token.colorBgLayout};
      display: flex;
      flex-direction: column;
    `,
    workareaHeader: css`
      box-sizing: border-box;
      height: 52px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 48px 0 28px;
      border-bottom: 1px solid ${token.colorBorder};
    `,
    headerTitle: css`
      font-weight: 600;
      font-size: 15px;
      color: ${token.colorText};
      display: flex;
      align-items: center;
      gap: 8px;
    `,
    headerButton: css`
      background-image: linear-gradient(78deg, #8054f2 7%, #3895da 95%);
      border-radius: 12px;
      height: 24px;
      width: 93px;
      display: flex;
      align-items: center;
      justify-content: center;
      color: #fff;
      cursor: pointer;
      font-size: 12px;
      font-weight: 600;
      transition: all 0.3s;
      &:hover {
        opacity: 0.8;
      }
    `,
    workareaBody: css`
      flex: 1;
      padding: 16px;
      background: ${token.colorBgContainer};
      border-radius: 16px;
      min-height: 0;
    `,
    bodyContent: css`
      overflow: auto;
      height: 100%;
      padding-right: 10px;
    `,
    bodyText: css`
      color: ${token.colorText};
      padding: 8px;
    `,
  };
});
const CopilotDemo = () => {
  const { styles: workareaStyles } = useWorkareaStyle();
  // ==================== State =================
  const [copilotOpen, setCopilotOpen] = useState(true);
  const [isCopilot,setIsCopilot] = useState(true);
  const [isNotContext,setIsNotContext] = useState(false);
  const [contextNumber,setContextNumber] = useState(1);
  const [nodes, setNodes] = useState([]);
  const [edges, setEdges] = useState([]);
  const [title, setTitle] = useState('');
  const [taskId,setTaskId] = useState('');
  const [taskStatus,setTaskStatus] = useState(0);
  // 初始化图数据
  // 初始化图数据
  const init_graphData = {
     nodes:nodes,
    edges: edges
  };

  // 状态用于存储当前选中的节点信息
  
  const [graphData, setGraphData] = useState(init_graphData);
  // 图的配置选项

  // 图的配置选项
  const options = {
    tooltip: {
      trigger: 'item',
      formatter: (params) => {
        if (params.dataType === 'node') {
          return `<div>
            <p><strong>节点名称：</strong>${params.data.name}</p>
            <p><strong>类型：</strong>${params.data.group}</p>
            <p><strong>描述：</strong>${params.data.group}</p>
          </div>`;
        }
        else{
          return `<div>${params.data.value}</div>`
        }
      },
    },
  series: [
    {
       type: 'graph',
        layout: 'force',
        symbolSize: 50,
        roam: true,
       
        label: {
        show: true,
        position: 'bottom',
        formatter: (params) => {
          return params.data.name;
        }
      },
        edgeSymbol: ['','arrow'],
        edgeSymbolSize: [4, 10],
        lineStyle: {
          color: '#888',
          curveness: 0.3,
          width: 2,
        },
        force: {
          repulsion: 8000,
          edgeLength: [100, 200],
          gravity: 0.1,
        },
        itemStyle: {
          borderColor: '#fff',
          borderWidth: 2,
          shadowBlur: 10,
          shadowColor: 'rgba(0, 0, 0, 0.3)',
        },
      data: nodes,
      // links: [],
      links: edges,
      lineStyle: {
        opacity: 0.9,
        width: 2,
        curveness: 0
      }
    }
  ],

  };


  // ==================== Render =================
  return (
    <div>
    <div className={workareaStyles.copilotWrapper}>
      {/** 左侧工作区 */}
      <div className={workareaStyles.workarea}>
        <div className={workareaStyles.workareaHeader}>
          <div className={workareaStyles.headerTitle}>
            <img
              src="https://mdn.alipayobjects.com/huamei_iwk9zp/afts/img/A*eco6RrQhxbMAAAAAAAAAAAAADgCCAQ/original"
              draggable={false}
              alt="logo"
              width={20}
              height={20}
            />
            知识图谱推理路径
          </div>
        </div>

        <div
          className={workareaStyles.workareaBody}
          style={{ margin: 16 }}
        >
          <Typography style={{fontSize:18,fontWeight:'bold',color:'#FF0000'}}>{title}</Typography>
          <div className={workareaStyles.bodyContent}>
      <ReactEcharts
        option={options}
        notMerge
        lazyUpdate
        style={{height:'calc(100vh - 150px)'}}
      />
          </div>
        </div>
      </div>
      {/** 右侧对话区 */}
      <Copilot 
        nodes={nodes}
        edges={edges}
        isCopilot={isCopilot}
        isNotContext={isNotContext}
        contextNumber={contextNumber}
        setContextNumber={setContextNumber}
        setIsCopilot={setIsCopilot}
        setIsNotContext={setIsNotContext}
        setNodes={setNodes}
        setEdges={setEdges}
        title={title}
        setTitle={setTitle}
        taskId={taskId}
        setTaskId={setTaskId}
        taskStatus={taskStatus}
        setTaskStatus={setTaskStatus}
        copilotOpen={copilotOpen} setCopilotOpen={setCopilotOpen} />
    </div>
    </div>
  );
};
export default CopilotDemo;