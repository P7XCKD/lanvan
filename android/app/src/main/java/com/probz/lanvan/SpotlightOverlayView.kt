package com.probz.lanvan

import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Path
import android.graphics.RectF
import android.os.Build
import android.util.AttributeSet
import android.view.View

/**
 * Custom overlay View for the Lanvan Production Onboarding Spotlight Walkthrough.
 * Dims the screen with a semi-transparent dark backdrop (72% dark), cuts out the exact
 * rounded rectangle around the targeted production control, and draws a subtle glowing
 * Lanvan blue (#8AB4F8) highlight ring around the target.
 */
class SpotlightOverlayView @JvmOverloads constructor(
    context: Context,
    attrs: AttributeSet? = null,
    defStyleAttr: Int = 0
) : View(context, attrs, defStyleAttr) {

    private var targetRect: RectF? = null
    private var targetRadiusPx: Float = 0f

    private val overlayPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.parseColor("#B8000000") // 72% translucent dark backdrop
    }

    private val strokePaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.parseColor("#8AB4F8") // Lanvan primary accent blue
        style = Paint.Style.STROKE
        strokeWidth = 2.5f * resources.displayMetrics.density
    }

    private val glowPaint = Paint(Paint.ANTI_ALIAS_FLAG).apply {
        color = Color.parseColor("#408AB4F8") // Subtle translucent outer glow
        style = Paint.Style.STROKE
        strokeWidth = 6.0f * resources.displayMetrics.density
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)
        val rect = targetRect
        val density = resources.displayMetrics.density

        if (rect != null && rect.width() > 0 && rect.height() > 0) {
            val saveCount = canvas.save()

            val path = Path().apply {
                addRoundRect(rect, targetRadiusPx, targetRadiusPx, Path.Direction.CW)
            }
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                canvas.clipOutPath(path)
            } else {
                @Suppress("DEPRECATION")
                canvas.clipPath(path, android.graphics.Region.Op.DIFFERENCE)
            }

            // Draw translucent dark backdrop outside the target cutout
            canvas.drawRect(0f, 0f, width.toFloat(), height.toFloat(), overlayPaint)
            canvas.restoreToCount(saveCount)

            // Draw outer subtle blue glow ring and sharp stroke ring around target
            canvas.drawRoundRect(rect, targetRadiusPx, targetRadiusPx, glowPaint)
            canvas.drawRoundRect(rect, targetRadiusPx, targetRadiusPx, strokePaint)
        } else {
            // No target (e.g. Step 5 / Ready step): Dim entire screen evenly
            canvas.drawRect(0f, 0f, width.toFloat(), height.toFloat(), overlayPaint)
        }
    }

    /**
     * Updates the highlight rectangle and border radius in local view coordinates.
     * Pass null or empty RectF to dim the backdrop without cutting out a target hole.
     */
    fun setHighlight(rect: RectF?, radiusDp: Float) {
        this.targetRect = rect
        this.targetRadiusPx = radiusDp * resources.displayMetrics.density
        invalidate()
    }
}
