# web_api.py
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from typing import Optional, List
import uvicorn
import PyPDF2
import docx
import io
import json
import anthropic
import os
from dotenv import load_dotenv
from pathlib import Path

# .env 파일 활성화 (명시적 경로 지정)
env_path = Path(__file__).parent / '.env'
load_dotenv()

# PDF 리포트 생성 관련 임포트
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from datetime import datetime
from notion_client import Client
import re

# OCR 관련 임포트
try:
    import pytesseract
    from pdf2image import convert_from_bytes
    from PIL import Image, ImageEnhance
    OCR_AVAILABLE = True
except ImportError:
    OCR_AVAILABLE = False
    print("⚠️ OCR 기능 비활성화: pytesseract 또는 pdf2image가 설치되지 않았습니다.")

# MCP 서버의 분석 함수들을 임포트
from index import (
    analyze_contract_risk,
    analyze_power_balance,
    analyze_power_balance_fast,
    calculate_power_score,
    analyze_power_balance_weighted
)

app = FastAPI(title="갑을관계 분석기 API")

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Anthropic API 클라이언트 초기화
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
if ANTHROPIC_API_KEY:
    anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    print("✅ Anthropic API 활성화")
    print(f"   🔑 API 키 앞부분: {ANTHROPIC_API_KEY[:20]}...")
else:
    anthropic_client = None
    print("⚠️ ANTHROPIC_API_KEY 환경 변수가 설정되지 않았습니다.")

# Notion 클라이언트 초기화
NOTION_TOKEN = os.getenv("NOTION_TOKEN")
NOTION_DATABASE_ID = "2b676661c12380cba76ecb36f00e24e6"

try:
    notion = Client(auth=NOTION_TOKEN)
    print("✅ Notion API 활성화")
except Exception as e:
    notion = None
    print(f"⚠️ Notion API 초기화 실패: {e}")

# 한글 폰트 설정 (Windows 기본 폰트)
try:
    # 맑은 고딕 폰트 경로
    FONT_PATH = "fonts/AppleGothic.ttf"
    FONT_BOLD_PATH = "fonts/AppleGothic.ttf"
    
    if os.path.exists(FONT_PATH):
        pdfmetrics.registerFont(TTFont('Malgun', FONT_PATH))
        if os.path.exists(FONT_BOLD_PATH):
            pdfmetrics.registerFont(TTFont('MalgunBold', FONT_BOLD_PATH))
        print("✅ PDF 한글 폰트 로드 완료")
    else:
        print("⚠️ 맑은 고딕 폰트를 찾을 수 없습니다. PDF에서 한글이 깨질 수 있습니다.")
except Exception as e:
    print(f"⚠️ 폰트 로드 실패: {e}")

# Tesseract와 Poppler 경로 설정
if OCR_AVAILABLE:
    # Tesseract 경로 (Windows 기본 설치 경로)
    TESSERACT_PATH = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    if os.path.exists(TESSERACT_PATH):
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH
        print("✅ Tesseract OCR 활성화")
    else:
        print(f"⚠️ Tesseract를 찾을 수 없습니다: {TESSERACT_PATH}")
        OCR_AVAILABLE = False
    
    # Poppler 경로 (여러 가능한 경로 시도)
    POPPLER_PATHS = [
        r'C:\poppler-25.11.0\Library\bin',
        r'C:\poppler\Library\bin',
        r'C:\poppler\bin',
        r'C:\Program Files\poppler\Library\bin',
    ]
    
    POPPLER_PATH = None
    for path in POPPLER_PATHS:
        if os.path.exists(path):
            POPPLER_PATH = path
            print(f"✅ Poppler 활성화: {path}")
            break
    
    if not POPPLER_PATH:
        print("⚠️ Poppler를 찾을 수 없습니다. OCR 기능이 제한될 수 있습니다.")

# 요청 모델
class ContractAnalysisRequest(BaseModel):
    contract_text: str

class RiskFinding(BaseModel):
    category: str
    severity: str
    matched_text: str
    location: Optional[str] = None

class RiskAnalysisRequest(BaseModel):
    findings: List[RiskFinding]

class PowerBalanceFastRequest(BaseModel):
    employee_indicators: List[str]
    employer_indicators: List[str]

class PowerScoreRequest(BaseModel):
    employee_obligations_count: int
    employer_rights_count: int

class PowerItem(BaseModel):
    text: str
    severity: str

class PowerBalanceWeightedRequest(BaseModel):
    employee_items: List[PowerItem]
    employer_items: List[PowerItem]

# 파일 텍스트 추출 함수
def extract_text_from_pdf(file_content: bytes) -> str:
    """PDF 파일에서 텍스트 추출 (OCR 포함)"""
    try:
        # 1단계: 일반 텍스트 추출 시도 (PyPDF2)
        pdf_file = io.BytesIO(file_content)
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        
        print(f"\n📄 PDF 정보:")
        print(f"   - 페이지 수: {len(pdf_reader.pages)}")
        
        for page_num, page in enumerate(pdf_reader.pages):
            try:
                page_text = page.extract_text()
                if page_text and page_text.strip():
                    text += page_text + "\n"
                    print(f"   ✅ {page_num + 1}페이지: {len(page_text)}자 추출")
                else:
                    print(f"   ⚠️ {page_num + 1}페이지: 텍스트 없음")
            except Exception as e:
                print(f"   ❌ {page_num + 1}페이지 오류: {e}")
                continue
        
        text = text.strip()
        
        # 2단계: 텍스트가 부족하면 OCR 시도
        suspicious_chars = sum(1 for c in text if (ord(c) > 0x1100 and ord(c) < 0x11FF) or c in '■□▪▫◾◽●○◦•∙·')
        corrupt_check = '\\' in text[:100] if len(text) > 100 else False
        is_corrupted = len(text) > 0 and (suspicious_chars / len(text) > 0.1 or corrupt_check)
        
        if len(text) < 100:
            print(f"   📊 추출된 텍스트: {len(text)}자 (부족)")
            
            if not OCR_AVAILABLE:
                raise HTTPException(
                    status_code=400,
                    detail="이 PDF는 이미지 기반이지만 OCR이 설치되지 않았습니다. 텍스트를 직접 복사해서 입력해주세요."
                )
            
            print("   🔍 OCR로 텍스트 추출 시도...")
            text = extract_text_with_ocr(file_content)
        else:
            print(f"   ✅ 추출 완료: {len(text)}자")
        
        # 3단계: 여전히 텍스트가 없으면 에러
        if not text or len(text) < 10:
            raise HTTPException(
                status_code=400,
                detail="PDF에서 텍스트를 추출할 수 없습니다. 파일이 손상되었거나 보호되어 있을 수 있습니다."
            )
        
        return text
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ PDF 처리 오류: {e}")
        raise HTTPException(status_code=400, detail=f"PDF 처리 오류: {str(e)}")


def extract_text_with_ocr(file_content: bytes) -> str:
    """이미지 기반 PDF에서 OCR로 텍스트 추출"""
    if not OCR_AVAILABLE:
        raise HTTPException(
            status_code=400,
            detail="OCR 기능을 사용할 수 없습니다. pytesseract와 pdf2image를 설치하세요."
        )
    
    try:
        print("   🖼️ OCR 처리 시작...")
        
        # PDF를 이미지로 변환 (해상도 높이기)
        if POPPLER_PATH:
            images = convert_from_bytes(
                file_content, 
                poppler_path=POPPLER_PATH,
                dpi=300
            )
        else:
            images = convert_from_bytes(file_content, dpi=300)
        
        print(f"   📸 {len(images)}개 이미지로 변환 완료")
        
        text = ""
        for i, image in enumerate(images):
            try:
                # 이미지 전처리 (선명하게)
                # 명암 대비 증가
                enhancer = ImageEnhance.Contrast(image)
                image = enhancer.enhance(2.0)
                
                # 선명도 증가
                enhancer = ImageEnhance.Sharpness(image)
                image = enhancer.enhance(2.0)
                
                # OCR 설정 개선
                custom_config = r'--oem 3 --psm 6'
                
                # OCR로 텍스트 추출 (한글+영어 혼합)
                page_text = pytesseract.image_to_string(
                    image, 
                    lang='kor+eng',
                    config=custom_config
                )
                
                if page_text and page_text.strip():
                    text += page_text + "\n"
                    print(f"   ✅ OCR {i + 1}페이지: {len(page_text)}자")
                else:
                    print(f"   ⚠️ OCR {i + 1}페이지: 텍스트 없음")
            except Exception as e:
                print(f"   ❌ OCR {i + 1}페이지 오류: {e}")
                continue
        
        text = text.strip()
        print(f"   ✅ OCR 완료: 총 {len(text)}자")
        
        if not text:
            raise HTTPException(
                status_code=400,
                detail="OCR로 텍스트를 추출할 수 없습니다. 이미지 품질이 낮거나 텍스트가 없을 수 있습니다."
            )
        
        return text
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"   ❌ OCR 오류: {e}")
        
        if "poppler" in str(e).lower() or "Unable to get page count" in str(e):
            raise HTTPException(
                status_code=400,
                detail="Poppler가 설치되지 않았거나 경로가 잘못되었습니다."
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"OCR 처리 오류: {str(e)}"
            )


def extract_text_from_docx(file_content: bytes) -> str:
    """DOCX 파일에서 텍스트 추출"""
    try:
        docx_file = io.BytesIO(file_content)
        doc = docx.Document(docx_file)
        text = "\n".join([paragraph.text for paragraph in doc.paragraphs])
        
        if not text or not text.strip():
            raise HTTPException(
                status_code=400,
                detail="DOCX 파일이 비어있습니다."
            )
        
        print(f"✅ DOCX 추출: {len(text)}자")
        return text.strip()
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ DOCX 처리 오류: {e}")
        raise HTTPException(status_code=400, detail=f"DOCX 처리 오류: {str(e)}")


def extract_text_from_txt(file_content: bytes) -> str:
    """TXT 파일에서 텍스트 추출"""
    try:
        # UTF-8 시도
        try:
            text = file_content.decode('utf-8').strip()
        except UnicodeDecodeError:
            # CP949 (한글 Windows) 시도
            try:
                text = file_content.decode('cp949').strip()
            except UnicodeDecodeError:
                # EUC-KR 시도
                text = file_content.decode('euc-kr').strip()
        
        if not text:
            raise HTTPException(
                status_code=400,
                detail="TXT 파일이 비어있습니다."
            )
        
        print(f"✅ TXT 추출: {len(text)}자")
        return text
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ TXT 처리 오류: {e}")
        raise HTTPException(status_code=400, detail=f"TXT 처리 오류: {str(e)}")


# PDF 리포트 생성 함수
def generate_pdf_report(analysis_result: dict, contract_text: str) -> bytes:
    """분석 결과를 PDF 리포트로 생성"""
    buffer = io.BytesIO()
    
    # PDF 문서 생성
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=20*mm,
        leftMargin=20*mm,
        topMargin=20*mm,
        bottomMargin=20*mm
    )
    
    # 스타일 설정
    styles = getSampleStyleSheet()
    
    # 한글 스타일 추가
    title_style = ParagraphStyle(
        'KoreanTitle',
        parent=styles['Title'],
        fontName='MalgunBold' if 'MalgunBold' in pdfmetrics.getRegisteredFontNames() else 'Helvetica-Bold',
        fontSize=24,
        textColor=colors.HexColor('#06b6d4'),
        spaceAfter=12
    )
    
    heading_style = ParagraphStyle(
        'KoreanHeading',
        parent=styles['Heading1'],
        fontName='MalgunBold' if 'MalgunBold' in pdfmetrics.getRegisteredFontNames() else 'Helvetica-Bold',
        fontSize=16,
        textColor=colors.HexColor('#0ea5e9'),
        spaceAfter=10,
        spaceBefore=10
    )
    
    body_style = ParagraphStyle(
        'KoreanBody',
        parent=styles['BodyText'],
        fontName='Malgun' if 'Malgun' in pdfmetrics.getRegisteredFontNames() else 'Helvetica',
        fontSize=10,
        leading=14
    )
    
    # 문서 요소들
    elements = []
    
    # 제목
    elements.append(Paragraph("갑을관계 분석 리포트", title_style))
    elements.append(Spacer(1, 10*mm))
    
    # 날짜
    date_text = f"분석 일시: {datetime.now().strftime('%Y년 %m월 %d일 %H:%M')}"
    elements.append(Paragraph(date_text, body_style))
    elements.append(Spacer(1, 10*mm))
    
    # 1. 종합 점수
    elements.append(Paragraph("1. 종합 분석 결과", heading_style))
    
    balance_score = analysis_result.get('balance_score', 0)
    total_risk = analysis_result.get('total_risk', 0)
    balance_status = analysis_result.get('balance_status', '알 수 없음')
    risk_level = analysis_result.get('risk_level', '알 수 없음')
    
    summary_data = [
        ['항목', '점수', '상태'],
        ['갑을 관계 균형도', f'{balance_score:.1f} / 10.0', balance_status],
        ['총 위험도', str(total_risk), risk_level]
    ]
    
    summary_table = Table(summary_data, colWidths=[60*mm, 50*mm, 60*mm])
    summary_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e293b')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'MalgunBold' if 'MalgunBold' in pdfmetrics.getRegisteredFontNames() else 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f1f5f9')),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Malgun' if 'Malgun' in pdfmetrics.getRegisteredFontNames() else 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
    ]))
    
    elements.append(summary_table)
    elements.append(Spacer(1, 10*mm))
    
    # 2. 주요 위험 요소
    risks = analysis_result.get('risks', [])
    if risks:
        elements.append(Paragraph("2. 주요 위험 요소", heading_style))
        
        for i, risk in enumerate(risks[:10], 1):  # 최대 10개만
            risk_title = f"{i}. {risk.get('category', '알 수 없음')}"
            elements.append(Paragraph(risk_title, ParagraphStyle(
                'RiskTitle',
                parent=body_style,
                fontName='MalgunBold' if 'MalgunBold' in pdfmetrics.getRegisteredFontNames() else 'Helvetica-Bold',
                fontSize=11,
                textColor=colors.HexColor('#dc2626')
            )))
            
            severity = risk.get('severity', 'unknown')
            risk_score = risk.get('risk_score', 0)
            location = risk.get('location', '위치 미상')
            matched_text = risk.get('matched_text', '')
            
            elements.append(Paragraph(f"• 심각도: {severity} (위험도: {risk_score})", body_style))
            elements.append(Paragraph(f"• 위치: {location}", body_style))
            
            if matched_text:
                elements.append(Paragraph(f"• 해당 조항: \"{matched_text[:200]}...\"", ParagraphStyle(
                    'Clause',
                    parent=body_style,
                    fontSize=9,
                    textColor=colors.HexColor('#475569'),
                    leftIndent=5*mm
                )))
            
            elements.append(Spacer(1, 5*mm))
    
    # 3. 개선 권장사항
    recommendations = analysis_result.get('recommendations', [])
    if recommendations:
        elements.append(PageBreak())
        elements.append(Paragraph("3. 개선 권장사항", heading_style))
        
        for i, rec in enumerate(recommendations, 1):
            rec_text = f"{i}. {rec}"
            elements.append(Paragraph(rec_text, body_style))
            elements.append(Spacer(1, 3*mm))
    
#     # 4. 계약서 원문 (일부)
#     elements.append(PageBreak())
#     elements.append(Paragraph("4. 계약서 원문 (처음 1000자)", heading_style))
#     
#     contract_preview = contract_text[:1000] + "..."
#     elements.append(Paragraph(contract_preview, ParagraphStyle(
#         'Contract',
#         parent=body_style,
#         fontSize=8,
# #         textColor=colors.HexColor('#64748b'),
# #         leftIndent=3*mm,
# #         rightIndent=3*mm
#     )))
    
    # PDF 생성
    doc.build(elements)
    
    buffer.seek(0)
    return buffer.getvalue()


# Claude + MCP 분석 함수
async def analyze_with_claude_mcp(contract_text: str) -> dict:
    """Claude API를 통해 MCP 도구로 계약서 분석"""
    if not anthropic_client:
        raise HTTPException(
            status_code=500,
            detail="Anthropic API 키가 설정되지 않았습니다. ANTHROPIC_API_KEY 환경 변수를 설정하세요."
        )
    
    try:
        print(f"\n🤖 Claude + MCP 분석 시작 (텍스트 길이: {len(contract_text)}자)")
        
        # ⭐ 수정된 프롬프트 - 점수 기준 명확화
        response = anthropic_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            temperature=0.0,  # ⭐ 이 줄 추가! #정확도 향상
            messages=[
                {
                    "role": "user",
                    "content": f"""당신은 계약서 분석 전문가입니다. 다음 계약서를 분석하고, 반드시 JSON 형식으로 결과를 반환해주세요.

계약서 내용:
{contract_text}

분석 단계:
1. 계약서에서 "갑"(고용주/발주자)의 권리 조항들을 찾으세요
2. 계약서에서 "을"(근로자/수급자)의 의무 조항들을 찾으세요  
3. 각 조항의 심각도를 평가하세요 (critical/high/medium/low)
4. gap-eul-analyzer의 analyze_power_balance_weighted 도구를 사용하세요
5. 위험 요소를 찾아 analyze_contract_risk 도구를 사용하세요

**점수 기준 (매우 중요!):**

1. balance_score (갑을 관계 균형도):
   - 반드시 0.0 ~ 10.0 사이의 숫자여야 합니다
   - 10점 만점 기준입니다
   - 점수별 의미:
     * 0-2점: 매우 불리함 (을에게 극도로 불리한 계약)
     * 2-4점: 불리함 (을에게 상당히 불리한 계약)
     * 4-6점: 보통 (약간 불리하거나 보통 수준)
     * 6-8점: 균형적 (비교적 공정한 계약)
     * 8-10점: 매우 균형적 (매우 공정한 계약)

2. total_risk (총 위험도):
   - 모든 위험 요소의 위험 점수를 합산한 값
   - 점수가 높을수록 위험함
   - 점수별 의미:
     * 0-29점: 낮음 (비교적 안전한 계약)
     * 30-39점: 보통 (일부 주의 필요)
     * 40-49점: 높음 (조항 수정 권장)
     * 50점 이상: 매우 높음 (계약 재검토 필요)

**중요한 원칙:**
- balance_score가 낮으면 (0-4점) → total_risk는 높아야 함 (30점 이상)
- balance_score가 높으면 (6-10점) → total_risk는 낮아야 함 (40점 미만)
- 두 점수는 반대 관계여야 합니다!

**중요: 반드시 아래 JSON 형식으로만 응답하세요. 다른 설명은 포함하지 마세요.**

{{
  "contract_type": "계약서 유형",
  "balance_score": 0.0,
  "balance_status": "상태 (매우 불리함/불리함/보통/균형적/매우 균형적)",
  "total_risk": 0,
  "risk_level": "위험도 (매우 높음/높음/보통/낮음)",
  "risks": [
    {{
      "category": "위험 요소 이름",
      "severity": "critical/high/medium/low",
      "matched_text": "해당 조항 원문",
      "location": "조항 위치",
      "risk_score": 0
    }}
  ],
  "recommendations": [
    "권장사항 1",
    "권장사항 2"
  ],
  "employer_advantages": ["갑의 권리 1", "갑의 권리 2"],
  "employee_obligations": ["을의 의무 1", "을의 의무 2"]
}}

JSON만 출력하세요. balance_score는 반드시 0-10 사이여야 합니다."""
                }
            ]
        )
        
        # Claude 응답 처리
        result_text = response.content[0].text.strip()
        
        print(f"✅ Claude 분석 완료")
        print(f"   - 응답 길이: {len(result_text)}자")
        
        # JSON 추출 (마크다운 코드 블록 제거)
        if result_text.startswith("```json"):
            result_text = result_text.replace("```json", "").replace("```", "").strip()
        elif result_text.startswith("```"):
            result_text = result_text.replace("```", "").strip()
        
        # JSON 파싱 시도
        try:
            result = json.loads(result_text)
            print(f"   ✅ JSON 파싱 성공")
            
            # ⭐ 점수 검증 및 정규화
            balance_score = result.get('balance_score', 0)
            
            # 0-10 범위 확인
            if balance_score > 10:
                print(f"   ⚠️ 균형도 점수가 10을 초과함: {balance_score} → 10.0으로 조정")
                result['balance_score'] = 10.0
            elif balance_score < 0:
                print(f"   ⚠️ 균형도 점수가 0 미만: {balance_score} → 0.0으로 조정")
                result['balance_score'] = 0.0
            
            print(f"   📊 최종 점수: 균형도 {result['balance_score']}/10.0, 위험도 {result.get('total_risk', 0)}")
            
            return result
        except json.JSONDecodeError as e:
            print(f"   ⚠️ JSON 파싱 실패: {e}")
            print(f"   📄 응답 내용 (처음 500자):\n{result_text[:500]}")
            
            # JSON이 아니면 텍스트 그대로 반환
            return {
                "analysis": result_text,
                "raw_response": True,
                "balance_score": 0.0,
                "total_risk": 0,
                "risks": [],
                "recommendations": []
            }
        
    except Exception as e:
        print(f"❌ Claude 분석 오류: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Claude 분석 중 오류가 발생했습니다: {str(e)}"
        )


# API 엔드포인트
@app.get("/")
async def root():
    return {
        "message": "갑을관계 분석기 API",
        "version": "3.2.0",
        "ocr_available": OCR_AVAILABLE,
        "claude_mcp_available": anthropic_client is not None,
        "pdf_report_available": True,
        "notion_export_available": notion is not None,
        "features": [
            "PDF 텍스트 추출",
            "PDF OCR (이미지 기반)" if OCR_AVAILABLE else "PDF OCR (비활성화)",
            "DOCX 지원",
            "TXT 지원",
            "Claude + MCP 고급 분석" if anthropic_client else "Claude + MCP (비활성화)",
            "PDF 리포트 다운로드",
            "Notion 내보내기" if notion else "Notion 내보내기 (비활성화)"
        ],
        "endpoints": {
            "/analyze/risk": "계약서 위험 요소 분석 (기본)",
            "/analyze/power-balance": "갑을 관계 균형도 분석 (짧은 문서)",
            "/analyze/power-balance-fast": "갑을 관계 균형도 분석 (긴 문서)",
            "/analyze/power-score": "갑을 균형 점수 계산",
            "/analyze/power-balance-weighted": "갑을 관계 분석 (가중치 반영)",
            "/analyze/with-mcp": "Claude + MCP 고급 분석 (추천) ⭐",
            "/upload": "파일 업로드 및 텍스트 추출",
            "/download-report": "분석 결과 PDF 리포트 다운로드 ⭐",
            "/export-notion": "Notion으로 내보내기 ⭐"
        }
    }

@app.post("/export-notion")
async def export_to_notion(request: dict):
    """분석 결과를 Notion 데이터베이스에 저장"""
    
    if not notion:
        raise HTTPException(
            status_code=500,
            detail="Notion API가 초기화되지 않았습니다."
        )
    
    try:
        analysis_result = request.get("analysis_result", {})
        contract_text = request.get("contract_text", "")
        file_name = request.get("file_name", "")  # ⭐ 파일명 받기
        
        if not analysis_result:
            raise HTTPException(status_code=400, detail="분석 결과가 없습니다.")
        
        print(f"\n📤 Notion 저장 시작...")
        
        # UUID 형식으로 변환 (대시 추가)
        db_id = NOTION_DATABASE_ID
        if len(db_id) == 32:  # 대시가 없는 경우
            db_id = f"{db_id[:8]}-{db_id[8:12]}-{db_id[12:16]}-{db_id[16:20]}-{db_id[20:]}"
        
        # 페이지 본문 내용 구성
        children = []
        
#         # 1. 계약서 원문 섹션
#         children.append({
#             "object": "block",
#             "type": "heading_2",
#             "heading_2": {
#                 "rich_text": [{"type": "text", "text": {"content": "계약서 원문"}}]
#             }
#         })
#         
#         # 계약서 텍스트를 2000자로 제한
#         contract_preview = contract_text[:2000] if len(contract_text) > 2000 else contract_text
#         
#         # 텍스트를 줄 단위로 분할하여 추가
#         for line in contract_preview.split('\n'):
#             if line.strip():
#                 children.append({
#                     "object": "block",
#                     "type": "paragraph",
#                     "paragraph": {
#                         "rich_text": [{"type": "text", "text": {"content": line[:2000]}}]
#                     }
#                 })
#         
        # 2. 분석 결과 요약 섹션
        children.append({
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [{"type": "text", "text": {"content": "분석 결과 요약"}}]
            }
        })
        
        # 점수 정보
        balance_score = analysis_result.get('balance_score', 0)
        total_risk = analysis_result.get('total_risk', 0)
        balance_status = analysis_result.get('balance_status', '알 수 없음')
        risk_level = analysis_result.get('risk_level', '알 수 없음')
        
        children.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"type": "text", "text": {"content": f"균형도: {balance_score} / 10.0 ({balance_status})"}}]
            }
        })
        
        children.append({
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"type": "text", "text": {"content": f"총 위험도: {total_risk} ({risk_level})"}}]
            }
        })
        
        # 3. 위험 요소 목록 섹션
        risks = analysis_result.get('risks', [])
        if risks:
            children.append({
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"type": "text", "text": {"content": "위험 요소 목록"}}]
                }
            })
            
            for i, risk in enumerate(risks[:10], 1):  # 최대 10개
                # 위험 요소 제목
                category = risk.get('category', 'N/A')
                severity = risk.get('severity', 'unknown')
                
                children.append({
                    "object": "block",
                    "type": "heading_3",
                    "heading_3": {
                        "rich_text": [{"type": "text", "text": {"content": f"{i}. {category} (심각도: {severity})"}}]
                    }
                })
                
                # 설명
                matched_text = risk.get('matched_text', '')
                if matched_text:
                    children.append({
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [{"type": "text", "text": {"content": f"해당 조항: {matched_text[:500]}"}}]
                        }
                    })
                
                location = risk.get('location', '')
                if location:
                    children.append({
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [{"type": "text", "text": {"content": f"위치: {location}"}}]
                        }
                    })
        
        # 4. 개선 권장사항
        recommendations = analysis_result.get('recommendations', [])
        if recommendations:
            children.append({
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"type": "text", "text": {"content": "개선 권장사항"}}]
                }
            })
            
            for rec in recommendations:
                children.append({
                    "object": "block",
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {
                        "rich_text": [{"type": "text", "text": {"content": rec[:2000]}}]
                    }
                })
        
        # Notion 페이지 생성
        now = datetime.now()
        
        # ⭐ 제목에 파일명 포함
        if file_name:
            page_title = f"{now.strftime('%Y-%m-%d')} ({file_name})"
        else:
            page_title = f"계약서 분석 - {now.strftime('%Y-%m-%d %H:%M')}"
        
        # 상태 값 매핑 (매우 균형적 추가!)
        status_value = balance_status if balance_status in ["매우 불리함", "불리함", "보통", "균형적", "매우 균형적"] else "보통"
        risk_value = risk_level if risk_level in ["매우 높음", "높음", "보통", "낮음"] else "보통"

        new_page = notion.pages.create(
            parent={"database_id": db_id},
            properties={
                "제목": {
                    "title": [
                        {
                            "text": {
                                "content": page_title
                            }
                        }
                    ]
                },
                "분석일시": {
                    "date": {
                        "start": now.isoformat()
                    }
                },
                "균형도 점수": {
                    "number": float(balance_score)
                },
                "총 위험도": {
                    "number": int(total_risk)
                },
                "상태": {
                    "select": {
                        "name": status_value
                    }
                },
                "위험 수준": {
                    "select": {
                        "name": risk_value
                    }
                }
            },
            children=children
        )
        
        print(f"✅ Notion 저장 완료: {new_page['url']}")
        
        return {
            "success": True,
            "page_id": new_page["id"],
            "page_url": new_page["url"],
            "message": "Notion에 성공적으로 저장되었습니다."
        }
        
    except Exception as e:
        print(f"❌ Notion 저장 오류: {e}")
        raise HTTPException(status_code=500, detail=f"Notion 저장 중 오류 발생: {str(e)}")

@app.post("/analyze/with-mcp")
async def api_analyze_with_mcp(request: ContractAnalysisRequest):
    """Claude + MCP를 사용한 고급 분석 (추천)"""
    try:
        result = await analyze_with_claude_mcp(request.contract_text)
        return JSONResponse(content=result)
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ MCP 분석 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/download-report")
async def download_report(request: dict):
    """분석 결과를 PDF 리포트로 다운로드"""
    try:
        analysis_result = request.get('analysis_result', {})
        contract_text = request.get('contract_text', '')
        
        if not analysis_result:
            raise HTTPException(status_code=400, detail="분석 결과가 없습니다.")
        
        print(f"\n📄 PDF 리포트 생성 중...")
        pdf_bytes = generate_pdf_report(analysis_result, contract_text)
        print(f"✅ PDF 생성 완료: {len(pdf_bytes):,} bytes")
        
        # 파일명 생성
        filename = f"gap_eul_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
        
    except Exception as e:
        print(f"❌ PDF 생성 오류: {e}")
        raise HTTPException(status_code=500, detail=f"PDF 생성 오류: {str(e)}")


@app.post("/analyze/risk")
async def api_analyze_risk(request: RiskAnalysisRequest):
    """계약서 위험 요소 분석"""
    try:
        findings_dict = [finding.dict() for finding in request.findings]
        result = analyze_contract_risk(findings_dict)
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/analyze/power-balance")
async def api_analyze_power_balance(request: ContractAnalysisRequest):
    """갑을 관계 균형도 분석 (짧은 문서용)"""
    try:
        if len(request.contract_text) > 5000:
            raise HTTPException(
                status_code=400,
                detail="텍스트가 너무 깁니다. 5000자 이하로 줄이거나 /analyze/power-balance-fast를 사용하세요."
            )
        result = analyze_power_balance(request.contract_text)
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/analyze/power-balance-fast")
async def api_analyze_power_balance_fast(request: PowerBalanceFastRequest):
    """갑을 관계 균형도 분석 (긴 문서용)"""
    try:
        result = analyze_power_balance_fast(
            request.employee_indicators,
            request.employer_indicators
        )
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/analyze/power-score")
async def api_calculate_power_score(request: PowerScoreRequest):
    """갑을 균형 점수 계산"""
    try:
        result = calculate_power_score(
            request.employee_obligations_count,
            request.employer_rights_count
        )
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/analyze/power-balance-weighted")
async def api_analyze_power_balance_weighted(request: PowerBalanceWeightedRequest):
    """갑을 관계 분석 (가중치 반영) - 추천"""
    try:
        employee_items_dict = [item.dict() for item in request.employee_items]
        employer_items_dict = [item.dict() for item in request.employer_items]
        
        result = analyze_power_balance_weighted(
            employee_items_dict,
            employer_items_dict
        )
        return JSONResponse(content=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """파일 업로드 및 텍스트 추출 (OCR 지원)"""
    try:
        file_content = await file.read()
        filename = file.filename.lower()
        
        print(f"\n📁 파일 업로드: {file.filename} ({len(file_content):,} bytes)")
        
        # 파일 형식에 따라 텍스트 추출
        if filename.endswith('.pdf'):
            text = extract_text_from_pdf(file_content)
        elif filename.endswith('.docx'):
            text = extract_text_from_docx(file_content)
        elif filename.endswith('.txt'):
            text = extract_text_from_txt(file_content)
        else:
            raise HTTPException(
                status_code=400,
                detail="지원하지 않는 파일 형식입니다. PDF, DOCX, TXT 파일만 업로드 가능합니다."
            )
        
        return {
            "filename": file.filename,
            "text": text,
            "length": len(text),
            "message": "텍스트 추출 완료"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ 파일 처리 실패: {e}")
        raise HTTPException(status_code=500, detail=f"파일 처리 오류: {str(e)}")


@app.get("/health")
async def health_check():
    """헬스 체크"""
    return {
        "status": "healthy",
        "ocr_available": OCR_AVAILABLE,
        "claude_mcp_available": anthropic_client is not None,
        "pdf_report_available": True,
        "notion_export_available": notion is not None,
        "tesseract_path": TESSERACT_PATH if OCR_AVAILABLE else None,
        "poppler_path": POPPLER_PATH if OCR_AVAILABLE else None
    }


if __name__ == "__main__":
    print("\n" + "="*50)
    print("🚀 갑을관계 분석기 API 서버")
    print("="*50)
    print(f"OCR 사용 가능: {'✅ Yes' if OCR_AVAILABLE else '❌ No'}")
    print(f"Claude + MCP: {'✅ Yes' if anthropic_client else '❌ No (API 키 필요)'}")
    print(f"PDF 리포트: ✅ Yes")
    print(f"Notion 내보내기: {'✅ Yes' if notion else '❌ No'}")
    if OCR_AVAILABLE:
        print(f"Tesseract: {TESSERACT_PATH if os.path.exists(TESSERACT_PATH) else '❌ 찾을 수 없음'}")
        print(f"Poppler: {POPPLER_PATH if POPPLER_PATH else '❌ 찾을 수 없음'}")
    print("="*50 + "\n")
    
    uvicorn.run(app, host="0.0.0.0", port=8000)
