document.addEventListener("DOMContentLoaded", function () {
    const buyNowBtn = document.getElementById("buy-now-btn");
    const otpModal = document.getElementById("otp-modal");
    const verifyOtpBtn = document.getElementById("verify-otp-btn");
    const resendOtpBtn = document.getElementById("resend-otp-btn");
    const cancelOtpBtn = document.getElementById("cancel-otp-btn");
    const otpInput = document.getElementById("otp-input");
    const emailField = document.getElementById("email");
    const placeOrderBtn = document.getElementById("place-order-btn");

    let resendCooldown = false;

    // ✅ Show OTP Modal & Send OTP
    buyNowBtn.addEventListener("click", function () {
        const email = emailField.value.trim();
        if (!email) {
            alert("Please enter your email before proceeding.");
            return;
        }

        fetch("/send-otp", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email: email }),
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                otpModal.style.display = "flex";
                alert("OTP sent to your email!");
            } else {
                alert(data.message || "Failed to send OTP");
            }
        })
        .catch(error => console.error("Error sending OTP:", error));
    });

    // ✅ Verify OTP
    verifyOtpBtn.addEventListener("click", function () {
        const otp = otpInput.value.trim();
        const email = emailField.value.trim();

        if (!otp || otp.length !== 6) {
            alert("Enter a valid 6-digit OTP");
            return;
        }

        fetch("/verify-otp", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email: email, otp: otp }),
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert("OTP verified successfully!");
                otpModal.style.display = "none";
                placeOrderBtn.disabled = false; // ✅ Enable Place Order button
            } else {
                alert(data.message || "Invalid OTP");
            }
        })
        .catch(error => console.error("Error verifying OTP:", error));
    });

    // ✅ Resend OTP
    resendOtpBtn.addEventListener("click", function () {
        if (resendCooldown) {
            alert("Please wait before resending OTP.");
            return;
        }

        const email = emailField.value.trim();
        fetch("/send-otp", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email: email }),
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                alert("OTP resent successfully!");
                resendCooldown = true;
                resendOtpBtn.disabled = true;
                setTimeout(() => {
                    resendCooldown = false;
                    resendOtpBtn.disabled = false;
                }, 30000); // 30 seconds cooldown
            } else {
                alert(data.message || "Failed to resend OTP");
            }
        })
        .catch(error => console.error("Error resending OTP:", error));
    });

    // ✅ Cancel OTP Modal
    cancelOtpBtn.addEventListener("click", function () {
        otpModal.style.display = "none";
        placeOrderBtn.disabled = true; // Disable order until verified
        otpInput.value = "";
    });
});
