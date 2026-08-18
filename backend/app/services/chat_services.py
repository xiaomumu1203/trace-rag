
import base64
import json
from typing import AsyncGenerator, List

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder, PromptTemplate
from langchain_classic.chains.history_aware_retriever import create_history_aware_retriever
from langchain_classic.chains.retrieval import create_retrieval_chain
from langchain_classic.chains.combine_documents import create_stuff_documents_chain


from app.models.chat import Message
from sqlalchemy.orm import Session

from app.models.knowledge_base import Document, KnowledgeBase
from app.services.embeddig.embedding_factory import EmbeddingFactory
from app.services.vector_store.factory import VectorStoreFactory
from app.services.hybrid_retriever import HybridRetriever
from app.core.config import settings
from app.services.llm.llm_factory import LLMFactory
from app.services.chat_memory import chat_memory


async def generate_response(
        query: str, 
        knowledge_base_ids: List[int], 
        chat_id: int, 
        user_id: int,
        db: Session
)-> AsyncGenerator[str, None]:
    bot_message: Message | None = None

    try:
        recent_messages = await chat_memory.get_or_load(chat_id, db)
        #创建用户消息记录
        user_message = Message(
            content=query,
            role="user",
            chat_id=chat_id
        )
        db.add(user_message)
        db.commit()
        await chat_memory.append(chat_id, "user", query)

        # 先插入一条空的机器人消息占位，AI 生成完成后会填充内容
        bot_message = Message(
            content="",
            role="assistant",
            chat_id=chat_id
        )
        
        db.add(bot_message)
        db.commit()

        #获得知识库和文档信息
        knowledge_bases = (
            db.query(KnowledgeBase)
            .filter(KnowledgeBase.id.in_(knowledge_base_ids)).
            all()
        )
        #初始化向量模型
        llm = LLMFactory.create()
        embeddings = EmbeddingFactory().create()

        #为每一个知识库创建一个向量数据库实例
        vector_stores = []
        for kb in knowledge_bases:
            documents = db.query(Document).filter(Document.knowledge_base_id == kb.id).all()
            if documents:
                vector_store = VectorStoreFactory.create(
                    store_type=settings.VECTOR_STORE_TYPE,
                    collection_name=f"kb_{kb.id}",
                    embeddings_function=embeddings
                )
                vector_stores.append(vector_store)

        if not vector_stores:
            error_msg = "没有任何知识库可以回答你的问题。"
            yield f'0:"{error_msg}"\n'                     # 发送错误消息（数据行）
            yield 'd:{"finishReason":"stop","usage":{"promptTokens":0,"completionTokens":0}}\n'  # 发送结束标记
            bot_message.content = error_msg                # 保存到机器人消息记录
            db.commit()
            return

        # 调用向量数据库进行检索
        retriever = HybridRetriever(
            vector_stores=vector_stores,
            db=db,
            knowledge_base_ids=[kb.id for kb in knowledge_bases],
            candidate_k=20,
            final_k=3,
            rrf_k=60,
        )

        #LLM初始化
        # 创建"问题重写"的提示词
        contextualize_q_system_prompt = (
            "给定一段聊天历史和用户的最新问题，"
            "如果最新问题引用了聊天历史中的上下文，"
            "请将其重写为一个不依赖聊天历史就能理解的独立问题。"
            "不要回答这个问题，"
            "只在需要时重写它，否则保持原样返回。"
        )
        contextualize_q_prompt = ChatPromptTemplate.from_messages(
            [
                SystemMessage(content=contextualize_q_system_prompt),
                MessagesPlaceholder(variable_name="chat_history"),
                ("human", "{input}"),
            ]
        )

        # 创建能感知对话历史的检索器：先用 LLM 重写问题，再检索
        history_aware_retriever = create_history_aware_retriever(
            llm, 
            retriever,
            contextualize_q_prompt
        )


        qa_system_prompt = (
            "你会收到一个用户问题，请给出清晰、简洁、准确的回答。"
            "你会收到一组与问题相关的上下文资料，这些资料按顺序从 1 开始编号。"
            "每段上下文根据其在数组中的位置有一个隐式的引用编号（第一段是 1，第二段是 2，以此类推）。"
            "请使用这些上下文来回答，并在适用的句子末尾用 [citation:x] 的格式标注引用来源。"
            "你的回答必须正确、准确，并以专业、中立的口吻撰写。"
            "请将回答控制在 1024 个 token 以内。不要提供与问题无关的信息，也不要重复。"
            "如果给定的上下文资料不足以回答，请说 'information is missing on'（缺少相关信息），后跟相关主题。"
            "如果一句话引用了多段上下文，请列出所有适用的引用，如 [citation:1][citation:2]。"
            "除代码、特定名称和引用标注外，你的回答必须使用与问题相同的语言。"
            "请保持简洁。\n\n上下文资料: {context}\n\n"
            "记住：请根据上下文的编号位置引用（第一段是 1，第二段是 2，以此类推），不要盲目逐字照搬上下文。"
        )

        qa_prompt = ChatPromptTemplate.from_messages(
            [
                ("system", qa_system_prompt),
                MessagesPlaceholder(variable_name="chat_history"),
                ("human", "{input}"),
            ]
        )

        # 修改 create_stuff_documents_chain 来自定义 context 格式
        document_prompt = PromptTemplate.from_template("\n\n- {page_content}\n\n")

        # 创建问答链
        question_answer_chain = create_stuff_documents_chain(
            llm,
            qa_prompt,
            document_variable_name="context",
            document_prompt=document_prompt
        )

        #创建检索链
        rag_chain = create_retrieval_chain(
            history_aware_retriever,
            question_answer_chain
        )

        # 生成回答
        chat_history = []
        for message in recent_messages:
            if message["role"] == "user":
                chat_history.append(HumanMessage(content=message["content"]))
            elif message["role"] == "assistant":
                if "__LLM_RESPONSE__" in message["content"]:
                    # 如果是 LLM 的响应占位符，跳过
                    message["content"] = message["content"].split("__LLM_RESPONSE__")[1]
                chat_history.append(AIMessage(content=message["content"]))

        full_response = ""
        answer_response = ""
        knowledge_base_names: dict[int, str] = {
            knowledge_base.id: knowledge_base.name for knowledge_base in knowledge_bases
        }

        async for chunk in rag_chain.astream({
            "input": query,
            "chat_history": chat_history
        }):
            if "context" in chunk:
                serializable_context = []
                for index, context in enumerate(chunk["context"], start=1):
                    context_metadata = context.metadata or {}
                    raw_kb_id = context_metadata.get("kb_id")
                    normalized_kb_id = (
                        int(raw_kb_id)
                        if isinstance(raw_kb_id, (int, str)) and str(raw_kb_id).isdigit()
                        else None
                    )
                    serializable_doc = {
                        "index": index,
                        "page_content": context.page_content,
                        "metadata": context_metadata,
                        "knowledge_base_name": (
                            knowledge_base_names.get(normalized_kb_id)
                            if normalized_kb_id is not None
                            else None
                        ),
                        "file_name": context_metadata.get("file_name"),
                    }
                    serializable_context.append(serializable_doc)
                escaped_context = json.dumps(
                    {"context": serializable_context},
                    ensure_ascii=False,
                    default=str,
                )

                # 转成 base64
                base64_context = base64.b64encode(escaped_context.encode()).decode()

                # 连接符号
                separator = "__LLM_RESPONSE__"

                full_response += base64_context + separator
                yield f"c:{json.dumps(serializable_context, ensure_ascii=False)}\n"

            if "answer" in chunk:
                answer_chunk = chunk["answer"]
                full_response += answer_chunk
                answer_response += answer_chunk
                # 转义引号并使用 json.dumps 正确处理特殊字符
                yield f"0:{json.dumps(answer_chunk, ensure_ascii=False)}\n"

        # 将完整的回答保存到数据库中的机器人消息记录
        bot_message.content = full_response
        db.commit()
        await chat_memory.append(chat_id, "assistant", answer_response)

        
    except Exception as e:
        error_message = f"Error generating response: {str(e)}"
        print(error_message)
        yield f"0:{json.dumps(error_message)}\n"
        yield 'd:{"finishReason":"error","usage":{"promptTokens":0,"completionTokens":0}}\n'
        
        # 将错误信息保存到数据库中的机器人消息记录
        if bot_message is not None:
            bot_message.content = error_message
            db.commit()
    finally:
        db.close()
