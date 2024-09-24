document.addEventListener('DOMContentLoaded', function () {
    // Auto-hide flash messages after 5 seconds
    setTimeout(function () {
      var flashMessage = document.getElementById('flash-message');
      if (flashMessage) {
        flashMessage.style.transition = 'opacity 1s';
        flashMessage.style.opacity = '0';
        setTimeout(function () {
          flashMessage.style.display = 'none';
        }, 1000);
      }
    }, 5000); // Adjust the time (in milliseconds) as needed

    

  }); 

