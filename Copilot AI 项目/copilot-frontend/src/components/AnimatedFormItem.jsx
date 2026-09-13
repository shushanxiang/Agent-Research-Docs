import { Form, Input } from 'antd';
import { motion } from 'framer-motion';

const errorVariants = {
  hidden: { opacity: 0, y: -10 },
  visible: { opacity: 1, y: 0 }
};

export default function AnimatedFormItem({ children, ...props }) {
  return (
    <Form.Item
      {...props}
      validateStatus={props.help ? 'error' : ''}
      help={
        <motion.div
          initial="hidden"
          animate={props.help ? 'visible' : 'hidden'}
          variants={errorVariants}
        >
          {props.help}
        </motion.div>
      }
    >
      {children}
    </Form.Item>
  );
}