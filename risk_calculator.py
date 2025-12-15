# -*- coding: utf-8 -*-
"""
위험도 점수 계산 모듈

역할: LLM이 찾아낸 위험 요소들을 받아서 점수를 계산합니다.
입력: 위험 요소 리스트 (category, severity, 원문)
출력: 총점, 등급, 카테고리별 점수
"""

# 기본 위험 요소별 가중치
RISK_WEIGHTS = {
    "unilateral_termination": 30,      # 일방적 해지권
    "excessive_damages": 25,           # 과도한 손해배상
    "copyright_transfer": 20,          # 저작권 강탈
    "unclear_scope": 15,               # 모호한 업무 범위
    "payment_delay": 10                # 대금 지급 지연
}

# 심각도별 배수
SEVERITY_MULTIPLIER = {
    "critical": 1.5,   # 치명적
    "high": 1.2,       # 높음
    "medium": 1.0,     # 중간
    "low": 0.7         # 낮음
}

def calculate_risk_score(findings):
    """
    위험도 점수 계산
    
    Args:
        findings: LLM이 찾아낸 위험 요소 리스트
        [
            {
                "category": "unilateral_termination",
                "severity": "critical",
                "matched_text": "갑은 사유 없이 해지할 수 있다",
                "location": "제3조"
            }
        ]
    
    Returns:
        {
            "total_score": 75,
            "grade": "D (위험)",
            "category_scores": {...},
            "findings_with_impact": [...]
        }
    """
    
    if not findings:
        return {
            "total_score": 0,
            "grade": "A (안전)",
            "category_scores": {},
            "findings_with_impact": []
        }
    
    total_score = 0
    category_scores = {}
    findings_with_impact = []
    
    for finding in findings:
        category = finding.get("category", "")
        severity = finding.get("severity", "medium")
        
        # 기본 가중치
        base_weight = RISK_WEIGHTS.get(category, 10)
        
        # 심각도 배수 적용
        multiplier = SEVERITY_MULTIPLIER.get(severity, 1.0)
        
        # 최종 점수
        impact_score = int(base_weight * multiplier)
        total_score += impact_score
        
        # 카테고리별 점수 누적
        if category in category_scores:
            category_scores[category] += impact_score
        else:
            category_scores[category] = impact_score
        
        # 영향도 정보 추가
        finding_copy = finding.copy()
        finding_copy["impact_score"] = impact_score
        findings_with_impact.append(finding_copy)
    
    # 최대 100점으로 제한
    total_score = min(total_score, 100)
    
    # 등급 계산
    grade = _calculate_grade(total_score)
    
    return {
        "total_score": total_score,
        "grade": grade,
        "category_scores": category_scores,
        "findings_with_impact": findings_with_impact
    }

def _calculate_grade(score):
    """점수를 등급으로 변환"""
    if score >= 80:
        return "F (매우 위험)"
    elif score >= 60:
        return "D (위험)"
    elif score >= 40:
        return "C (주의 필요)"
    elif score >= 20:
        return "B (보통)"
    else:
        return "A (안전)"

def get_category_name_kr(category):
    """카테고리 영문명을 한글로 변환"""
    category_names = {
        "unilateral_termination": "일방적 해지권",
        "excessive_damages": "과도한 손해배상",
        "copyright_transfer": "저작권 강탈",
        "unclear_scope": "모호한 업무 범위",
        "payment_delay": "대금 지급 지연"
    }
    return category_names.get(category, category)


# 테스트 코드
if __name__ == "__main__":
    # 테스트용 샘플 데이터
    test_findings = [
        {
            "category": "unilateral_termination",
            "severity": "critical",
            "matched_text": "갑은 언제든지 사유 없이 해지할 수 있다",
            "location": "제3조"
        },
        {
            "category": "excessive_damages",
            "severity": "high",
            "matched_text": "위약 시 계약금의 300%를 배상한다",
            "location": "제5조"
        }
    ]
    
    result = calculate_risk_score(test_findings)
    
    print("=== 위험도 분석 결과 ===")
    print(f"총점: {result['total_score']}점")
    print(f"등급: {result['grade']}")
    print(f"\n카테고리별 점수:")
    for cat, score in result['category_scores'].items():
        print(f"  - {get_category_name_kr(cat)}: {score}점")
