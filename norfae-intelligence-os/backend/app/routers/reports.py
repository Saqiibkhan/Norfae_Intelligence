from fastapi import APIRouter, Depends

from fastapi.responses import StreamingResponse

from sqlalchemy.orm import Session

from datetime import datetime, timedelta

from app.core.dependencies import get_db

from app.services.reporting_service import ReportingService

from app.exports.excel_exporter import ExcelExporter

from app.exports.pdf_exporter import PDFExporter

router = APIRouter(prefix="/reports", tags=["Reports"])

# ===================================
# GENERATE REPORT
# ===================================


@router.get("/generate")
def generate_report(
    report_type: str = "business",
    start_date: str = None,
    end_date: str = None,
    db: Session = Depends(get_db),
):

    try:

        # ===============================
        # DEFAULT
        # ===============================

        start = None

        end = None

        # ===============================
        # DATE FILTER
        # ===============================

        if start_date and end_date:

            start = datetime.strptime(start_date, "%Y-%m-%d")

            end = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)

        # ===============================
        # GENERATE REPORT
        # ===============================

        report = ReportingService.generate_report(
            db=db, report_type=report_type, start_date=start, end_date=end
        )

        return {"success": True, "report": report}

    except Exception as e:

        return {"success": False, "message": str(e)}


# ===================================
# EXPORT EXCEL
# ===================================


@router.get("/export/excel")
def export_excel(
    report_type: str = "business",
    start_date: str = None,
    end_date: str = None,
    db: Session = Depends(get_db),
):

    try:

        start = None

        end = None

        if start_date and end_date:

            start = datetime.strptime(start_date, "%Y-%m-%d")

            end = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)

        report = ReportingService.generate_report(
            db=db, report_type=report_type, start_date=start, end_date=end
        )

        excel_file = ExcelExporter.generate_business_report(report)

        return StreamingResponse(
            excel_file,
            media_type=(
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            ),
            headers={"Content-Disposition": "attachment; filename=norfae_report.xlsx"},
        )

    except Exception as e:

        return {"success": False, "message": str(e)}


# ===================================
# EXPORT PDF
# ===================================


@router.get("/export/pdf")
def export_pdf(
    report_type: str = "business",
    start_date: str = None,
    end_date: str = None,
    db: Session = Depends(get_db),
):

    try:

        start = None

        end = None

        if start_date and end_date:

            start = datetime.strptime(start_date, "%Y-%m-%d")

            end = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)

        report = ReportingService.generate_report(
            db=db, report_type=report_type, start_date=start, end_date=end
        )

        pdf_file = PDFExporter.generate_business_report(report)

        return StreamingResponse(
            pdf_file,
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=norfae_report.pdf"},
        )

    except Exception as e:

        return {"success": False, "message": str(e)}
