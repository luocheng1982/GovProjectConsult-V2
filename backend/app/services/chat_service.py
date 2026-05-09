import os
import glob
import shutil
from langchain_chroma import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_community.document_loaders import PyPDFLoader, TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.core.config import settings
from app.services.loaders import CustomDocxLoader, CustomDocLoader, CustomExcelLoader
from app.ocr.ocr_service import ocr_process

class ChatService:
    def __init__(self):
        # Initialize Embeddings (Same as ingest)
        # Use local cache directory
        cache_dir = os.path.join(settings.BASE_DIR, "data", "model_cache")
        self.embeddings = HuggingFaceEmbeddings(
            model_name=cache_dir
        )
        
        # Initialize Vector Store
        self.vectorstore = Chroma(
            persist_directory=settings.PERSIST_DIRECTORY,
            embedding_function=self.embeddings
        )
        
        # Initialize LLM (DeepSeek)
        self.llm = ChatOpenAI(
            model_name="deepseek-chat",
            openai_api_key=settings.OPENAI_API_KEY,
            openai_api_base=settings.OPENAI_API_BASE,
            temperature=0.3
        )

    def _clean_text(self, text: str) -> str:
        """Remove Markdown symbols like *, #, > to improve readability as requested."""
        import re
        # Remove bold/italic markers (* or **)
        text = re.sub(r'\*\*|__', '', text)
        text = re.sub(r'\*|_', '', text)
        # Remove headers (#)
        text = re.sub(r'#+', '', text)
        # Remove blockquotes (>)
        text = re.sub(r'>', '', text)
        # Remove code backticks
        text = re.sub(r'`', '', text)
        
        # Remove file extensions from citations like 《Filename.md》 or (Filename.pdf)
        # Pattern: 《 (chars) . (ext) 》 -> 《 (chars) 》
        text = re.sub(r'《([^》]+?)\.(?:md|pdf|docx|txt|xls|xlsx)》', r'《\1》', text)
        # Pattern: ( (chars) . (ext) ) -> ( (chars) )  -- be careful not to break sentences
        # Let's target specific common patterns if parentheses are used for source citation
        # Or just generic remove of .md .pdf inside Chinese text context might be safer?
        # Let's stick to the 《》 pattern first as that's the most common document citation style.
        
        return text

    async def get_response(self, query: str, file_content: str = None, project_type: str = "general") -> dict:
        try:
            # 1. Search Policies (High Priority)
            # Log the exact filter and query
            print(f"\n[RETRIEVAL DEBUG] Query: {query}")
            print(f"[RETRIEVAL DEBUG] Project Type from Request: {project_type}")
            
            # CRITICAL FIX: Ensure project_type is correctly handled
            # If front-end sends "general", but we want to be more inclusive, 
            # we already relaxed the policy_filter. 
            # However, let's log if there's any discrepancy.
            
            policy_filter = {
                "$and": [
                    {"type": {"$eq": "policy"}},
                    {"project_type": {"$eq": project_type}}
                ]
            }
            print(f"[RETRIEVAL DEBUG] Using Policy Filter: {policy_filter}")

            # Improved Keyword Extraction
            import re
            # 1. Extract "附件X"
            annex_matches = re.findall(r'附件\s*([0-9一二三四五六七八九十]+)', query)
            
            # 2. Extract core business terms
            raw_terms = re.findall(r'[\u4e00-\u9fa5]+', query)
            stop_words = {"有关", "说明", "查找", "关于", "请帮", "我想", "知道", "什么", "内容", "信息", "一下", "请问", "规定", "查询", "的", "中", "在", "关于", "对于", "如何", "是", "时"}
            
            keywords = []
            for term in raw_terms:
                if len(term) <= 1: continue
                if term not in stop_words:
                    keywords.append(term)
                    # If term is long, break it down
                    if len(term) > 3:
                        for i in range(len(term)-1):
                            sub = term[i:i+2]
                            if sub not in stop_words: keywords.append(sub)
            
            # Add specific mapping for common terms
            if any(k in query for k in ["增值税", "进项税", "发票", "抵扣", "剔除"]):
                keywords.extend(["增值税", "进项税", "发票", "抵扣", "剔除", "剔除规定"])

            if any(k in query for k in ["变更申请", "变更", "调整", "设备调整", "经费调整"]):
                keywords.extend(["变更", "调整", "变更申请", "资金用途调整", "设备调整", "经费调整"])
            
            if annex_matches:
                for am in annex_matches:
                    keywords.append(f"附件{am}")
                    keywords.append(f"附件 {am}")
            
            keywords = list(set(keywords))
            print(f"[RETRIEVAL DEBUG] Enhanced Keywords: {keywords}")

            # Semantic search
            policy_docs = self.vectorstore.similarity_search(
                query, 
                k=15, # Further increase k for more coverage
                filter=policy_filter
            )
            print(f"[RETRIEVAL DEBUG] Semantic docs found: {len(policy_docs)}")
            
            # Keyword Boost: Targeted search for key terms
            kw_matches = []
            search_keywords = [kw for kw in keywords if len(kw) >= 2]
            
            # CRITICAL TERMS: If these are found, they MUST be prioritized
            critical_terms = ["增值税", "进项税", "发票", "剔除", "抵扣", "附件1", "附件 1",
                              "变更", "变更申请", "调整", "资金用途调整", "设备调整", "经费调整"]
            has_critical_term = any(ct in query for ct in critical_terms)
            
            # Use a more aggressive contains search
            seen_content_in_kw = set()
            for kw in search_keywords[:15]: # Increase to 15 keywords
                # Directly query Chroma for content matches
                res = self.vectorstore._collection.get(
                    where={
                        "$and": [
                            {"type": {"$eq": "policy"}},
                            {"project_type": {"$eq": project_type}}
                        ]
                    },
                    where_document={"$contains": kw},
                    limit=30
                )
                
                if res and res['documents']:
                    for i, content in enumerate(res['documents']):
                        if content in seen_content_in_kw: continue
                        seen_content_in_kw.add(content)
                        
                        from langchain_core.documents import Document
                        metadata = res['metadatas'][i]
                        
                        match_doc = Document(page_content=content, metadata=metadata)
                        
                        # Score based on keyword density
                        score = sum(3 if k in content else 0 for k in keywords) # Increase weight
                        
                        # CRITICAL BOOST: If chunk contains critical terms from query
                        for ct in critical_terms:
                            if ct in query and ct in content:
                                score += 20
                        
                        # Bonus for annex matches
                        if any(f"附件{am}" in content or f"附件 {am}" in content for am in annex_matches):
                            score += 15
                            
                        kw_matches.append((match_doc, score))
            
            kw_matches.sort(key=lambda x: x[1], reverse=True)
            top_kw_docs = [m[0] for m in kw_matches[:12]]
            
            # Combine and deduplicate
            # If we have critical terms, put kw_matches first
            if has_critical_term:
                policy_docs = top_kw_docs + policy_docs
            else:
                policy_docs = top_kw_docs + policy_docs # Keep kw first anyway
            seen_content = set()
            unique_policy_docs = []
            for doc in policy_docs:
                if doc.page_content not in seen_content:
                    unique_policy_docs.append(doc)
                    seen_content.add(doc.page_content)
            
            policy_docs = unique_policy_docs[:15] # Keep more for AI to see

            # 跨项目检索：宝安区科创项目 -> 战略性新兴产业项目
            cross_project_docs = []
            cross_project_source = "战略性新兴产业项目"
            if project_type == "宝安区科创项目":
                print(f"[RETRIEVAL DEBUG] 跨项目检索: {project_type} -> {cross_project_source}")
                cross_filter = {
                    "$and": [
                        {"type": {"$eq": "policy"}},
                        {"project_type": {"$eq": cross_project_source}}
                    ]
                }
                cross_project_docs = self.vectorstore.similarity_search(
                    query,
                    k=10,
                    filter=cross_filter
                )
                print(f"[RETRIEVAL DEBUG] 跨项目检索到 {len(cross_project_docs)} 个文档")

                # 标记跨项目文档来源
                for doc in cross_project_docs:
                    doc.metadata["cross_project"] = cross_project_source

            # LOG: Final Top Sources for AI
            print(f"[RETRIEVAL DEBUG] Final context has {len(policy_docs)} chunks.")
            for i, d in enumerate(policy_docs[:5]):
                source_info = f"{d.metadata.get('source')} (Type: {d.metadata.get('project_type')})"
                print(f"[RETRIEVAL DEBUG] Top {i}: {source_info} | Content: {d.page_content[:100]}...")
            
            # 2. Search Cases (Reference)
            case_filter = {
                "$and": [
                    {"type": {"$eq": "case"}},
                    {"project_type": {"$eq": project_type}}
                ]
            }
            case_docs = self.vectorstore.similarity_search(
                query,
                k=3,
                filter=case_filter
            )
        except Exception as e:
            print(f"Vector search error: {e}")
            policy_docs = []
            case_docs = []
        
        # Collect sources for "View Source" feature
        sources = []
        for doc in policy_docs:
            sources.append({
                "filename": doc.metadata.get("source", "Unknown"),
                "content": doc.page_content,
                "type": doc.metadata.get("type", "policy")
            })
        for doc in cross_project_docs:
            sources.append({
                "filename": doc.metadata.get("source", "Unknown"),
                "content": doc.page_content,
                "type": "policy",
                "cross_project": cross_project_source
            })
        for doc in case_docs:
            sources.append({
                "filename": doc.metadata.get("source", "Unknown"),
                "content": doc.page_content,
                "type": doc.metadata.get("type", "case")
            })

        history_text = ""
        current_question = query
        marker = "【当前问题】"
        if marker in query:
            parts = query.rsplit(marker, 1)
            history_text = parts[0].strip()
            current_question = parts[1].strip()

        direct_doc = None
        if any(ct in current_question for ct in ["增值税", "进项税", "发票", "剔除", "抵扣", "附件1", "附件 1"]):
            for doc in policy_docs:
                content = doc.page_content
                if "增值税" in content and "进项税" in content and ("剔除" in content or "抵扣" in content):
                    direct_doc = doc
                    break

        if direct_doc:
            source = direct_doc.metadata.get("source", "Unknown")
            # Remove file extension for direct return path
            if '.' in source:
                source = source.rsplit('.', 1)[0]
            
            content = direct_doc.page_content
            target_phrases = ["项目单位取得的增值税专用发票", "进项税额不论是否发生实质抵扣", "进项税额不论是否发生实际抵扣"]
            snippet = content
            for phrase in target_phrases:
                idx = content.find(phrase)
                if idx != -1:
                    start = idx
                    end = min(len(content), idx + 180)
                    snippet = content[start:end]
                    break
            scenario = "general"
            if any(k in current_question for k in ["自筹", "自有资金", "配套资金"]):
                scenario = "self_funding"
            elif any(k in current_question for k in ["调整", "变更", "调减", "减少投资额", "资金结构"]):
                scenario = "adjust"
            if scenario == "self_funding":
                conclusion = "结论：上述条款适用于包括项目单位自筹资金在内的所有计入项目完成投资金额的支出。凡是形成可抵扣的增值税进项税额，无论是否实际抵扣，均应从项目完成投资金额中剔除，自筹资金形成的可抵扣进项税额同样不得计入项目完成投资。"
            elif scenario == "adjust":
                conclusion = "结论：上述条款在项目资金调整、项目变更或调减投资额时同样适用。测算调整后的项目完成投资和资助金额时，应先在原始和调整后的投资构成中分别剔除所有可抵扣进项税额，在“剔除可抵扣进项税后的金额”基础上比较和确认项目完成投资及资助额度。"
            else:
                conclusion = "结论：上述条款针对“项目单位取得的增值税专用发票”，并未区分资金来源或业务场景。凡是计入项目完成投资金额的支出，只要形成可抵扣的增值税进项税额，无论是否实际抵扣，均应从项目完成投资金额中剔除，作为统一的审计与验收口径。"
            answer = (
                "根据《" + source + "》附件1相关条款，原文要点如下：\n"
                + snippet + "\n\n"
                + conclusion
            )
            return {
                "answer": answer,
                "sources": sources
            }

        # 3. Construct Context
        context_parts = []
        if policy_docs:
            context_parts.append("【规章制度 (必须遵守)】:")
            for i, doc in enumerate(policy_docs, 1):
                source = doc.metadata.get("source", "Unknown")
                # Remove extension from source name
                if '.' in source:
                    source = source.rsplit('.', 1)[0]
                context_parts.append(f"{i}. (来源: {source}) {doc.page_content}")

        if cross_project_docs:
            context_parts.append(f"\n【参照规章制度 (来自{cross_project_source})】:")
            for i, doc in enumerate(cross_project_docs, 1):
                source = doc.metadata.get("source", "Unknown")
                if '.' in source:
                    source = source.rsplit('.', 1)[0]
                context_parts.append(f"{i}. (参照来源: {source}) {doc.page_content}")

        if case_docs:
            context_parts.append("\n【典型案例 (仅供参考)】:")
            for i, doc in enumerate(case_docs, 1):
                source = doc.metadata.get("source", "Unknown")
                # Remove extension from source name
                if '.' in source:
                    source = source.rsplit('.', 1)[0]
                context_parts.append(f"{i}. (来源: {source}) {doc.page_content}")
                
        full_context = "\n".join(context_parts)
        
        # 4. Generate Answer
        # Get list of all projects to help AI understand the scope
        all_docs = self.list_documents(project_type)
        
        system_prompt = (
            "你是一个专业的政府科技项目咨询助手。\n"
            "你的任务是根据提供的【参考资料】（规章制度和典型案例）回答用户的问题。\n\n"
            "重要指引：\n"
            "0. **严格限定范围**：你只能根据提供的【参考资料】内容进行回答。如果参考资料中没有提到用户询问的相关政策（例如用户询问河套地区政策，但参考资料中全是战略性新兴产业政策），你必须告知用户：'根据您当前选择的项目类型，知识库中未检索到相关政策规定。' 绝对不能凭记忆回答知识库之外的政策内容。\n"
            "0-2. **跨项目类型检索规则**：如果当前项目类型为「宝安区科创项目」，且在【参照规章制度】部分检索到了来自「战略性新兴产业项目」的政策内容，请注意：这些内容是「参照」性质，不是本项目类型的原有规定。在回答时，请明确说明「根据参照的《XXX》（来源：战略性新兴产业项目相关规定）...」，让用户清楚了解这是跨项目类型的引用。\n"
            
            "0-3. **宝安区科创项目增值税不适用规则**：如果当前项目类型为「宝安区科创项目」，当用户询问与「增值税」「进项税」「发票抵扣」「剔除进项税」等相关问题时，必须首先向用户说明：本项目类型为政府资助资金项目，不存在自筹费用，经费支出全部来自政府资助，不涉及增值税抵扣概念，因此不适用增值税相关政策规定。如果【参照规章制度】部分引用了来自「战略性新兴产业项目」的增值税相关规定，必须明确告知用户该规定仅供参照，不适用于本项目类型。\n"
            "1. **统一表述**：请在回答开头使用“根据当前知识库内容”作为引言，不要说“根据您提供的参考资料”。\n"
            "2. **精准定位附件**：用户提到的'附件'通常嵌套在大型政策文件中。即使文件名没有包含'附件1'，只要参考资料的内容中明确写着'附件1'、'项目验收专项审计工作规范'或涉及'增值税剔除'的规定，就说明这是用户寻找的依据。\n"
            "3. **内容优先原则**：如果参考资料中出现了'增值税'、'进项税'、'剔除'、'抵扣'等关键词，请务必以此内容为准。特别注意：在《验收实施细则》附件1中，明确规定'项目单位取得的增值税专用发票，可以抵扣的进项税额不论是否发生实质抵扣，均予以剔除'。如果资料中有这段文字，请务必直接引用，不要说找不到。\n"
            "4. **纠正混淆**：不要将不同文件的'第二十一条'混淆。如果资料中显示的'第二十一条'与增值税无关，而另一段包含'附件1'的内容正好提到了增值税，请优先回答增值税相关内容。\n"
            "5. **指明来源**：回答时请明确指出出处，例如：'根据《验收实施细则》附件1（项目验收专项审计工作规范）的规定...'。\n"
            "7. **文件名处理**：在提及具体文件名时，请务必去掉文件名后缀（如 .md, .pdf, .docx 等）。例如：应说《验收实施细则》，而不要说《验收实施细则.md》。\n"
            "8. **多轮对话聚焦**：用户消息中可能包含若干轮历史对话片段以及最后的当前问题。请先在心中用一两句话概括与当前问题直接相关的关键信息，尤其是时间节点（如“仅剩1个月”“已超过3个月申报期限”等）和前一轮已说明的具体情形，然后据此作答，回答中不要复述小结过程。\n"
            "9. **在既有规则基础上作出可操作的推理**：如果规章制度没有对用户设定的特殊情形给出直接条款（例如：制度要求“应提前3个月提出变更申请”，而用户描述的是“只剩1个月才发现核心成员离职”），请在遵守规章精神和边界的前提下，结合条款目的给出合理、具体、可执行的处理建议，并明确说明哪些属于规章原文规定，哪些属于在原文基础上的合理延伸，不要简单机械地重复通用流程。\n"
            "10. **处理“变更/调整”类问题**：如果参考资料中出现“变更申请”“变更备案”“调整资金用途”“设备调整”“经费调整”等条款（例如要求在合同到期日前若干时间内提出书面申请、由某管理机构负责审核调整、必要时组织专家评估并出具批复），你必须将这些条款视为主管部门收到变更申请后的处理流程，根据条款内容分步骤说明“受理→审核/评估→作出同意或不同意的决定”，不得回答“知识库中未检索到相关规定”。\n"
            "11. **禁止机械式否定**：只有在参考资料中完全没有出现与用户问题关键词相关的内容时（例如既没有“变更”“调整”“经费调整”“设备调整”等字样，也没有任何受理、审核、批复、变更申请等描述），才可以说明“根据当前知识库内容，未检索到关于××的具体规定”。一旦存在相关条款，你必须基于条款内容给出尽可能具体、可操作的回答，而不是简单宣称找不到。\n"
            "12. **变更合理性分析的重点维度**：当用户询问变更是否合理、是否可以支持时，请至少从以下几个方面进行分析，并在回答中逐点说明你的判断依据。分析时请避免仅用“你需要从哪些方面研判”的方式去指导用户，而是要直接针对本次变更给出你的专业判断，并在最后用“综合判断：……”一句话概括是否合理、是否建议同意变更以及需要重点关注的事项："
            "（1）对建设内容和目标的影响：判断变更后是否仍能完成原批复或合同约定的主要建设内容和建设目标，是否削弱关键功能或产出。"
            "（2）对绩效指标的影响：结合规程中约定的约束性指标和预期性指标，分析变更是否可能导致主要绩效指标难以完成，必要时提示需要同步调整相关指标或说明理由。"
            "（3）对资金结构和使用合规性的影响：包括经费调整是否在规程允许的比例范围内，是否改变了资金用途的性质，是否存在将建设性支出调整为日常支出等不合规情形。"
            "（4）对进度和实施周期的影响：如变更涉及延期或设备采购调整，说明是否需要“延长执行期”或“调整实施进度”，以及是否触及规程对延期次数和总期限的限制。"
            "（5）对合同和批复文件的影响：判断是否需要同步变更项目合同或批复文件中的建设内容、经费预算、绩效指标等条款，并提示应通过何种程序办理。"
            "（6）风险与审计关注点：指出该变更可能引发的主要风险（如资金闲置、资产闲置、目标弱化等），以及在后续审计、绩效评价或验收中可能被重点核查的事项，帮助用户提前做好说明或补充佐证材料。\n"
            "13. **引用完整性要求**：当检索到的参考资料包含具体条款编号时，你必须严格遵守以下规则：\n"
            "- 条款编号必须逐字引用，不得进行任何格式转换。例如：原文是'（一）'则回答'（一）'，不得改为'3.1'；原文是'第（一）款'则回答'第（一）款'，不得改为'第1.1款'。\n"
            "- 如果检索到'（一）至（十一）'共11项条款，你必须列出全部11项，不得合并为3项或6项。\n"
            "- 如果检索到的是'3.1 乙方负责...3.2 乙方应确保...'这种阿拉伯数字格式，则按原格式引用。\n"
            "- 绝对不得：用概括性描述替代具体条款编号，或用自己的话改写原文内容。\n"
            "违规示例：如果参考资料中写着'（一）深圳国际金融科技研究院的设立'，但你回答为'3.1 乙方负责研究院的日常运营'，这就是严重错误！\n"
        )
        
        user_content = f"当前项目类型: {project_type}\n"
        if all_docs:
            # Clean up filenames for display
            clean_filenames = []
            for d in all_docs[:20]:
                name = d['filename']
                # Remove extension for cleaner display
                if '.' in name:
                    name = name.rsplit('.', 1)[0]
                clean_filenames.append(name)
            user_content += f"知识库包含文件列表: {', '.join(clean_filenames)}\n\n"
        
        if full_context:
             user_content += f"【参考资料】:\n{full_context}\n\n"
        
        if file_content:
            user_content += f"用户上传文件内容摘要:\n{file_content[:5000]}...\n\n"
            system_prompt += (
                "6. 用户还上传了一份文件，请结合该文件内容进行回答。"
                "当用户的问题涉及“变更”或“调整”（例如经费及设备调整申请、项目变更申请等）时，"
                "请优先从上传文件中提取关键信息（如调整事项、调整金额及比例、原批复或合同中的对应内容、是否涉及负责人或核心成员变更、是否影响建设内容和目标等），"
                "并结合操作规程中对一般性变更和重大实质性变更的分类标准，明确判断该申请属于哪一类变更，写出判断依据。"
                "同时，请按照上述“变更合理性分析的重点维度”逐项进行评估：说明该申请是否会影响主要绩效指标完成、是否需要同步调整合同或批复条款、调整幅度是否在规程允许范围内、"
                "以及可能引发的资金合规性和审计风险，并在此基础上给出清晰的处理建议和注意事项。回答末尾必须单独列出“综合判断：……”一句，对本次变更的类型判定、合理性结论以及是否建议同意变更作出明确表态，如“综合判断：本次变更属于一般性变更，整体合理，建议在××条件下同意变更”。\n"
            )

        if history_text:
            user_content += f"历史对话片段（供你理解上下文，无需逐字复述）:\n{history_text}\n\n"

        user_content += f"当前用户问题: {current_question}"

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_content)
        ]
        
        response = self.llm.invoke(messages)
        final_answer = self._clean_text(response.content)

        context_for_validation = "\n".join([doc.page_content for doc in policy_docs])
        final_answer = self._validate_clause_references(final_answer, context_for_validation)

        return {
            "answer": final_answer,
            "sources": sources
        }

    def _validate_clause_references(self, answer: str, context: str) -> str:
        """Validate that clause references in the answer match the retrieved context.

        Detects hallucinated clause numbers (e.g., answering 3.1 when context has （一）).
        """
        import re

        if not context or not answer:
            return answer

        context_lower = context.lower()
        answer_lower = answer.lower()

        chinese_clause_pattern = re.compile(r'（[一二三四五六七八九十]+）')
        arabic_clause_pattern = re.compile(r'\b(\d+\.\d+)\b')

        context_has_chinese = bool(chinese_clause_pattern.search(context))
        context_has_arabic = bool(arabic_clause_pattern.search(context))

        answer_has_chinese = bool(chinese_clause_pattern.search(answer))
        answer_has_arabic = bool(arabic_clause_pattern.search(answer))

        if context_has_chinese and answer_has_arabic and not answer_has_chinese:
            warning = (
                "\n\n[系统提示：检测到回答可能存在条款编号格式不一致的问题。"
                "检索到的资料中使用的是中文数字条款编号（如（一）、（二）等）而非阿拉伯数字格式（如3.1、3.2）。"
                "请确保回答中的条款编号与原始资料一致。]"
            )
            return answer + warning

        return answer

    async def generate_id_from_name(self, name: str) -> str:
        """Generate a short English ID from a Chinese name using LLM."""
        system_prompt = (
            "You are a helpful assistant. "
            "Translate the following Chinese Project Name into a short, snake_case English Identifier. "
            "It will be used as a directory name and ID. "
            "Output ONLY the ID, no other text. "
            "Example: '人工智能专项' -> 'ai_special'"
        )
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=name)
        ]
        response = self.llm.invoke(messages)
        # Clean up response
        id_str = response.content.strip().lower().replace(" ", "_").replace("-", "_")
        # Remove any non-alphanumeric chars (except underscore)
        import re
        id_str = re.sub(r'[^a-z0-9_]', '', id_str)
        return id_str

    def delete_project_docs(self, project_type: str) -> bool:
        """Delete all documents for a project type from vector store."""
        try:
            self.vectorstore._collection.delete(where={"project_type": project_type})
            return True
        except Exception as e:
            print(f"Error deleting project docs: {e}")
            return False

    async def add_document(self, file_path: str, doc_type: str, project_type: str = "general") -> bool:
        """Add a single document to the vector store."""
        try:
            # 1. Load Document
            if file_path.lower().endswith(".pdf"):
                loader = PyPDFLoader(file_path)
                docs = loader.load()
                total_text = sum(len(doc.page_content.strip()) for doc in docs)
                if total_text < 50:
                    from langchain_core.documents import Document
                    ocr_result = ocr_process(file_path)
                    docs = [Document(page_content=ocr_result.get('full_text', ''), metadata={})]
            elif file_path.lower().endswith(".docx"):
                loader = CustomDocxLoader(file_path)
                docs = loader.load()
            elif file_path.lower().endswith(".doc"):
                loader = CustomDocLoader(file_path)
                docs = loader.load()
            elif file_path.lower().endswith(".xlsx") or file_path.lower().endswith(".xls"):
                loader = CustomExcelLoader(file_path)
                docs = loader.load()
            elif file_path.lower().endswith(".txt") or file_path.lower().endswith(".md"):
                loader = TextLoader(file_path, encoding="utf-8")
                docs = loader.load()
            else:
                raise ValueError(f"Unsupported file type: {os.path.basename(file_path)}")

            # 2. Add Metadata
            for doc in docs:
                doc.metadata["type"] = doc_type
                doc.metadata["source"] = os.path.basename(file_path)
                doc.metadata["project_type"] = project_type
            
            # 3. Split Text
            # Improved splitting strategy: recursive character splitting with regex for clauses and sections
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000, # Increased chunk size to keep context
                chunk_overlap=150,
                separators=["\n附件", "\n第", "\n一、", "\n（一）", "\n\n", "\n", "。", "；", " ", ""]
            )
            splits = text_splitter.split_documents(docs)
            
            # Add semantic markers if it's a policy
            if doc_type == "policy":
                import re
                clause_pattern = re.compile(r"(第[一二三四五六七八九十百]+[条|章])")
                for split in splits:
                    matches = clause_pattern.findall(split.page_content)
                    if matches:
                        # Append found clauses to metadata for better retrieval
                        split.metadata["clauses"] = ",".join(list(set(matches)))
            
            # 4. Add to Vector Store
            if splits:
                self.vectorstore.add_documents(splits)
            return True
        except Exception as e:
            print(f"Error adding document {file_path}: {e}")
            # Re-raise exception so endpoint can return detailed error
            raise e

    def list_documents(self, project_type: str = "general"):
        """List all documents in the knowledge base for a specific project type."""
        docs = []
        
        # Helper to scan directory
        def scan_dir(path, doc_type):
            if not os.path.exists(path):
                return
            for root, _, files in os.walk(path):
                for file in files:
                    if file.startswith('.'): continue
                    docs.append({
                        "filename": file,
                        "type": doc_type,
                        "path": os.path.join(root, file),
                        "project_type": project_type
                    })

        scan_dir(os.path.join(settings.DOCS_DIRECTORY, project_type, "policies"), "policy")
        scan_dir(os.path.join(settings.DOCS_DIRECTORY, project_type, "cases"), "case")
        return docs

    def delete_document(self, filename: str, doc_type: str, project_type: str = "general") -> bool:
        """Delete a document from disk and vector store."""
        # 1. Determine path
        subdir = "policies" if doc_type == "policy" else "cases"
        file_path = os.path.join(settings.DOCS_DIRECTORY, project_type, subdir, filename)
        
        # 2. Delete from Disk
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception as e:
                print(f"Error deleting file {file_path}: {e}")
                return False
        else:
            print(f"File not found: {file_path}")
            
        # 3. Delete from Vector Store (Chroma)
        try:
            # We need to filter by source AND project_type to be safe, though source is filename which might be unique enough if we don't have dupes.
            # But Chroma delete doesn't support complex AND logic easily in 'where' clause for some versions.
            # However, source should be unique per file path usually.
            # Wait, our ingest logic sets source = os.path.basename(file_path). 
            # If two project types have same filename, we have a problem deleting by source only.
            # Let's check ingest.py again.
            # doc.metadata["source"] = os.path.basename(file_path)
            # Yes, if project A and B both have "guide.pdf", deleting "guide.pdf" might delete both if we only filter by source.
            # We should filter by project_type too.
            self.vectorstore._collection.delete(where={"$and": [{"source": filename}, {"project_type": project_type}]})
            return True
        except Exception as e:
            print(f"Error deleting from vector store: {e}")
            return False

    async def analyze_document(self, content: str, filename: str) -> str:
        """Analyze a single document without RAG context (or with minimal RAG)."""
        system_prompt = "你是一个专业的文档分析助手。请总结以下文档的主要内容，并指出其中的关键信息。"
        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=f"文件名: {filename}\n内容:\n{content[:5000]}")
        ]
        response = self.llm.invoke(messages)
        return self._clean_text(response.content)
