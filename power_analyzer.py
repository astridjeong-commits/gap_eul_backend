# -*- coding: utf-8 -*-
"""
갑을 관계 분석 모듈 (최종 완성 버전)
- 긴 문서 처리 최적화
- 청크 분할 처리
- 심각도 가중치 반영
"""

EMPLOYER_RIGHTS_KEYWORDS = [
    "해지할 수 있다", "변경할 수 있다", "요구할 수 있다",
    "결정한다", "지시한다", "승인", "거부할 수 있다",
    "중단할 수 있다", "요청할 수 있다"
]

EMPLOYEE_OBLIGATIONS_KEYWORDS = [
    "하여야 한다", "의무를 진다", "책임을 진다",
    "배상", "금지", "제한", "승인을 받아야",
    "통보하여야", "준수하여야"
]

def analyze_power_balance(contract_text):
    """
    갑을 관계 균형도 분석 (기본 버전)
    
    Args:
        contract_text: 계약서 전문
    
    Returns:
        분석 결과 딕셔너리
    """
    if not contract_text:
        return {"error": "계약서 내용이 없습니다"}
    
    # 긴 문서는 자동으로 청크 처리
    if len(contract_text) > 1000:
        return analyze_power_balance_chunked(contract_text)
    
    employer_count = sum(
        contract_text.count(keyword) 
        for keyword in EMPLOYER_RIGHTS_KEYWORDS
    )
    
    employee_count = sum(
        contract_text.count(keyword) 
        for keyword in EMPLOYEE_OBLIGATIONS_KEYWORDS
    )
    
    if employer_count == 0:
        balance_ratio = employee_count
    else:
        balance_ratio = employee_count / employer_count
    
    power_level, fairness_score = _determine_power_level(balance_ratio)
    recommendations = _generate_recommendations(balance_ratio, employer_count, employee_count)
    
    return {
        "balance_ratio": round(balance_ratio, 2),
        "power_level": power_level,
        "employer_rights_count": employer_count,
        "employee_obligations_count": employee_count,
        "fairness_score": fairness_score,
        "recommendations": recommendations
    }

def analyze_power_balance_chunked(contract_text, chunk_size=500):
    """
    긴 계약서를 청크로 나눠서 처리 (방법 1)
    
    Args:
        contract_text: 계약서 전문
        chunk_size: 청크 크기 (기본 500자)
    
    Returns:
        분석 결과 딕셔너리
    """
    if len(contract_text) <= chunk_size:
        return analyze_power_balance(contract_text)
    
    # 조항별로 분할 시도
    if '제' in contract_text and '조' in contract_text:
        chunks = contract_text.split('제')
    else:
        # 조항이 없으면 단순 길이로 분할
        chunks = [contract_text[i:i+chunk_size] for i in range(0, len(contract_text), chunk_size)]
    
    total_employer = 0
    total_employee = 0
    
    for chunk in chunks:
        if not chunk.strip():
            continue
        
        employer_count = sum(chunk.count(kw) for kw in EMPLOYER_RIGHTS_KEYWORDS)
        employee_count = sum(chunk.count(kw) for kw in EMPLOYEE_OBLIGATIONS_KEYWORDS)
        
        total_employer += employer_count
        total_employee += employee_count
    
    if total_employer == 0:
        balance_ratio = total_employee
    else:
        balance_ratio = total_employee / total_employer
    
    power_level, fairness_score = _determine_power_level(balance_ratio)
    recommendations = _generate_recommendations(balance_ratio, total_employer, total_employee)
    
    return {
        "balance_ratio": round(balance_ratio, 2),
        "power_level": power_level,
        "employer_rights_count": total_employer,
        "employee_obligations_count": total_employee,
        "fairness_score": fairness_score,
        "recommendations": recommendations,
        "processing_method": "chunked"
    }

def calculate_power_balance_from_counts(employer_count, employee_count):
    """
    LLM이 이미 센 개수로 점수 계산 (방법 3)
    
    Args:
        employer_count: 갑의 권리 개수
        employee_count: 을의 의무 개수
    
    Returns:
        분석 결과 딕셔너리
    """
    if employer_count == 0:
        balance_ratio = employee_count
    else:
        balance_ratio = employee_count / employer_count
    
    power_level, fairness_score = _determine_power_level(balance_ratio)
    recommendations = _generate_recommendations(balance_ratio, employer_count, employee_count)
    
    return {
        "balance_ratio": round(balance_ratio, 2),
        "power_level": power_level,
        "employer_rights_count": employer_count,
        "employee_obligations_count": employee_count,
        "fairness_score": fairness_score,
        "recommendations": recommendations
    }

def calculate_power_balance_weighted(employer_items, employee_items):
    """
    심각도 가중치를 반영한 갑을 균형 분석 (최고 정확도)
    
    Args:
        employer_items: [{"text": "...", "severity": "critical/high/medium/low"}, ...]
        employee_items: [{"text": "...", "severity": "critical/high/medium/low"}, ...]
    
    Returns:
        분석 결과 딕셔너리
    """
    # 심각도별 가중치
    severity_weights = {
        "critical": 3.0,
        "high": 2.0,
        "medium": 1.0,
        "low": 0.5
    }
    
    # 가중 점수 계산
    employer_weighted = sum(
        severity_weights.get(item.get("severity", "medium"), 1.0)
        for item in employer_items
    )
    
    employee_weighted = sum(
        severity_weights.get(item.get("severity", "medium"), 1.0)
        for item in employee_items
    )
    
    # 실제 개수
    employer_count = len(employer_items)
    employee_count = len(employee_items)
    
    # 균형 비율 (가중치 반영)
    if employer_weighted == 0:
        balance_ratio = employee_weighted
    else:
        balance_ratio = employee_weighted / employer_weighted
    
    power_level, fairness_score = _determine_power_level(balance_ratio)
    recommendations = _generate_recommendations(balance_ratio, employer_count, employee_count)
    
    # 심각도별 상세 정보 추가
    severity_breakdown = _analyze_severity_breakdown(employer_items, employee_items)
    
    return {
        "balance_ratio": round(balance_ratio, 2),
        "power_level": power_level,
        "employer_rights_count": employer_count,
        "employee_obligations_count": employee_count,
        "employer_weighted_score": round(employer_weighted, 1),
        "employee_weighted_score": round(employee_weighted, 1),
        "fairness_score": fairness_score,
        "recommendations": recommendations,
        "severity_breakdown": severity_breakdown
    }

def _analyze_severity_breakdown(employer_items, employee_items):
    """심각도별 분류"""
    breakdown = {
        "employer": {"critical": 0, "high": 0, "medium": 0, "low": 0},
        "employee": {"critical": 0, "high": 0, "medium": 0, "low": 0}
    }
    
    for item in employer_items:
        severity = item.get("severity", "medium")
        breakdown["employer"][severity] = breakdown["employer"].get(severity, 0) + 1
    
    for item in employee_items:
        severity = item.get("severity", "medium")
        breakdown["employee"][severity] = breakdown["employee"].get(severity, 0) + 1
    
    return breakdown

def _determine_power_level(ratio):
    """균형 비율로 불공정도 판단"""
    if ratio > 3.0:
        return "갑 절대우위 (극도로 불공정)", 10
    elif ratio > 2.0:
        return "갑 우위 (매우 불공정)", 30
    elif ratio > 1.5:
        return "갑 우위 (불공정)", 50
    elif ratio > 1.2:
        return "약간 갑 우위", 70
    elif ratio >= 0.8:
        return "균형적", 90
    else:
        return "을 우위 (드문 경우)", 95

def _generate_recommendations(ratio, employer_count, employee_count):
    """불공정도에 따른 협상 제안 생성"""
    recommendations = []
    
    if ratio > 2.5:
        recommendations.extend([
            "[긴급] 이 계약서는 극도로 불공정합니다.",
            "[제안] 상호 해지권 명시를 강력히 요청하세요",
            "[제안] 손해배상 상한선 설정을 협의하세요",
            "[제안] 업무 범위를 구체적으로 명시할 것을 요구하세요"
        ])
    elif ratio > 2.0:
        recommendations.extend([
            "[주의] 계약서가 상당히 불공정합니다.",
            "[제안] 핵심 조항 재협상을 권장합니다",
            "[제안] 일방적 해지권 조항을 상호 조항으로 변경 요청"
        ])
    elif ratio > 1.5:
        recommendations.extend([
            "[검토] 일부 조항 검토가 필요합니다.",
            "[제안] 불리한 조항 2-3개를 선택해 협상하세요"
        ])
    else:
        recommendations.append("[안전] 비교적 균형잡힌 계약서입니다.")
    
    if employee_count > 30:
        recommendations.append(
            f"[경고] 을의 의무가 {employee_count}개로 과다합니다. 핵심 의무만 남기고 삭제 협의하세요."
        )
    
    if employer_count < 5 and employee_count > 10:
        recommendations.append(
            f"[경고] 갑의 의무가 {employer_count}개로 너무 적습니다. 상호 의무 조항 추가를 요청하세요."
        )
    
    return recommendations