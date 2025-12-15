# index.py
from typing import List, Dict, Any

def analyze_contract_risk(findings: List[Dict[str, Any]]) -> Dict[str, Any]:
    """계약서 위험 요소 분석 및 점수 계산"""
    
    # 카테고리별 가중치
    severity_weights = {
        "critical": 10,
        "high": 7,
        "medium": 4,
        "low": 2
    }
    
    category_names = {
        "unilateral_termination": "일방적 계약 해지",
        "excessive_damages": "과도한 손해배상",
        "copyright_transfer": "저작권 전면 이전",
        "unclear_scope": "불명확한 업무 범위",
        "payment_delay": "대금 지급 지연"
    }
    
    # 점수 계산
    total_score = 0
    category_counts = {}
    severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    
    for finding in findings:
        severity = finding.get("severity", "low")
        category = finding.get("category", "")
        
        # 점수 누적
        total_score += severity_weights.get(severity, 0)
        
        # 카테고리별 카운트
        category_counts[category] = category_counts.get(category, 0) + 1
        
        # 심각도별 카운트
        severity_counts[severity] += 1
    
    # 위험도 등급 결정
    if total_score >= 30:
        risk_level = "매우 위험"
        risk_color = "red"
    elif total_score >= 20:
        risk_level = "위험"
        risk_color = "orange"
    elif total_score >= 10:
        risk_level = "주의"
        risk_color = "yellow"
    else:
        risk_level = "양호"
        risk_color = "green"
    
    return {
        "total_score": total_score,
        "risk_level": risk_level,
        "risk_color": risk_color,
        "findings_count": len(findings),
        "severity_counts": severity_counts,
        "category_counts": category_counts,
        "category_names": category_names,
        "recommendations": [
            "전문가와 계약서 검토를 권장합니다." if total_score >= 20 else "계약 체결 전 신중한 검토가 필요합니다.",
            "불리한 조항에 대해 수정을 요청하세요." if severity_counts["critical"] > 0 else None,
            "계약서 작성 시 법률 자문을 받는 것을 고려하세요." if total_score >= 30 else None
        ]
    }


def analyze_power_balance(contract_text: str) -> Dict[str, Any]:
    """갑을 관계 균형도 분석 (짧은 문서용)"""
    
    # 갑(고용주)의 권리를 나타내는 키워드
    employer_keywords = [
        "갑은", "갑이", "발주자는", "발주자가", "회사는", "회사가",
        "임의로", "일방적으로", "언제든지", "즉시", "통보 없이",
        "해지할 수 있다", "중단할 수 있다", "변경할 수 있다",
        "지시", "명령", "요구", "승인", "결정"
    ]
    
    # 을(근로자)의 의무를 나타내는 키워드
    employee_keywords = [
        "을은", "을이", "수급자는", "수급자가", "프리랜서는", "프리랜서가",
        "반드시", "의무", "책임", "준수", "이행", "제출",
        "배상", "손해", "위약금", "벌금",
        "금지", "제한", "불가", "할 수 없다"
    ]
    
    # 키워드 카운트
    employer_count = sum(contract_text.count(keyword) for keyword in employer_keywords)
    employee_count = sum(contract_text.count(keyword) for keyword in employee_keywords)
    
    # 점수 계산
    total = employer_count + employee_count
    if total == 0:
        balance_score = 50
    else:
        balance_score = round((employee_count / total) * 100)
    
    # 균형도 판단
    if balance_score >= 70:
        balance_level = "을에게 매우 불리"
        balance_color = "red"
    elif balance_score >= 60:
        balance_level = "을에게 불리"
        balance_color = "orange"
    elif balance_score >= 40:
        balance_level = "균형적"
        balance_color = "green"
    elif balance_score >= 30:
        balance_level = "갑에게 불리"
        balance_color = "orange"
    else:
        balance_level = "갑에게 매우 불리"
        balance_color = "red"
    
    return {
        "balance_score": balance_score,
        "balance_level": balance_level,
        "balance_color": balance_color,
        "employer_rights_count": employer_count,
        "employee_obligations_count": employee_count,
        "analysis": f"계약서에서 갑의 권리 표현이 {employer_count}회, 을의 의무 표현이 {employee_count}회 발견되었습니다."
    }


def analyze_power_balance_fast(employee_indicators: List[str], employer_indicators: List[str]) -> Dict[str, Any]:
    """갑을 관계 균형도 분석 (긴 문서용 - LLM이 표현들을 찾아서 전달)"""
    
    employer_count = len(employer_indicators)
    employee_count = len(employee_indicators)
    
    total = employer_count + employee_count
    if total == 0:
        balance_score = 50
    else:
        balance_score = round((employee_count / total) * 100)
    
    # 균형도 판단
    if balance_score >= 70:
        balance_level = "을에게 매우 불리"
        balance_color = "red"
    elif balance_score >= 60:
        balance_level = "을에게 불리"
        balance_color = "orange"
    elif balance_score >= 40:
        balance_level = "균형적"
        balance_color = "green"
    elif balance_score >= 30:
        balance_level = "갑에게 불리"
        balance_color = "orange"
    else:
        balance_level = "갑에게 매우 불리"
        balance_color = "red"
    
    return {
        "balance_score": balance_score,
        "balance_level": balance_level,
        "balance_color": balance_color,
        "employer_rights_count": employer_count,
        "employee_obligations_count": employee_count,
        "employer_indicators": employer_indicators[:10],  # 상위 10개만
        "employee_indicators": employee_indicators[:10],   # 상위 10개만
        "analysis": f"갑의 권리 표현 {employer_count}개, 을의 의무 표현 {employee_count}개가 발견되었습니다."
    }


def calculate_power_score(employee_obligations_count: int, employer_rights_count: int) -> Dict[str, Any]:
    """갑을 균형 점수 계산 (초고속)"""
    
    total = employee_obligations_count + employer_rights_count
    if total == 0:
        balance_score = 50
    else:
        balance_score = round((employee_obligations_count / total) * 100)
    
    # 균형도 판단
    if balance_score >= 70:
        balance_level = "을에게 매우 불리"
        balance_color = "red"
    elif balance_score >= 60:
        balance_level = "을에게 불리"
        balance_color = "orange"
    elif balance_score >= 40:
        balance_level = "균형적"
        balance_color = "green"
    elif balance_score >= 30:
        balance_level = "갑에게 불리"
        balance_color = "orange"
    else:
        balance_level = "갑에게 매우 불리"
        balance_color = "red"
    
    return {
        "balance_score": balance_score,
        "balance_level": balance_level,
        "balance_color": balance_color,
        "employer_rights_count": employer_rights_count,
        "employee_obligations_count": employee_obligations_count
    }


def analyze_power_balance_weighted(employee_items: List[Dict[str, Any]], employer_items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """갑을 관계 분석 (심각도 가중치 반영) - 가장 정확"""
    
    # 심각도별 가중치
    severity_weights = {
        "critical": 4,  # 일방적/과도한
        "high": 3,      # 불리한
        "medium": 2,    # 보통
        "low": 1        # 경미한
    }
    
    # 가중치 점수 계산
    employer_score = sum(severity_weights.get(item.get("severity", "medium"), 2) for item in employer_items)
    employee_score = sum(severity_weights.get(item.get("severity", "medium"), 2) for item in employee_items)
    
    total_score = employer_score + employee_score
    if total_score == 0:
        balance_score = 50
    else:
        balance_score = round((employee_score / total_score) * 100)
    
    # 균형도 판단
    if balance_score >= 70:
        balance_level = "을에게 매우 불리"
        balance_color = "red"
        recommendation = "계약서에 을에게 과도하게 불리한 조항이 많습니다. 전문가와 상담 후 재협상을 강력히 권장합니다."
    elif balance_score >= 60:
        balance_level = "을에게 불리"
        balance_color = "orange"
        recommendation = "을에게 불리한 조항들이 있습니다. 주요 조항에 대한 수정을 요청하세요."
    elif balance_score >= 40:
        balance_level = "균형적"
        balance_color = "green"
        recommendation = "비교적 균형잡힌 계약서입니다. 세부 조항을 꼼꼼히 확인하세요."
    elif balance_score >= 30:
        balance_level = "갑에게 불리"
        balance_color = "orange"
        recommendation = "갑에게 불리한 조항들이 있습니다."
    else:
        balance_level = "갑에게 매우 불리"
        balance_color = "red"
        recommendation = "갑에게 과도하게 불리한 계약서입니다."
    
    # 심각도별 카운트
    employee_severity = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    employer_severity = {"critical": 0, "high": 0, "medium": 0, "low": 0}
    
    for item in employee_items:
        severity = item.get("severity", "medium")
        employee_severity[severity] += 1
    
    for item in employer_items:
        severity = item.get("severity", "medium")
        employer_severity[severity] += 1
    
    return {
        "balance_score": balance_score,
        "balance_level": balance_level,
        "balance_color": balance_color,
        "employer_weighted_score": employer_score,
        "employee_weighted_score": employee_score,
        "employer_rights_count": len(employer_items),
        "employee_obligations_count": len(employee_items),
        "employer_severity_breakdown": employer_severity,
        "employee_severity_breakdown": employee_severity,
        "recommendation": recommendation,
        "employer_items_sample": employer_items[:5],  # 상위 5개 샘플
        "employee_items_sample": employee_items[:5]   # 상위 5개 샘플
    }