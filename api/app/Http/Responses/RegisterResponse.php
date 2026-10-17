<?php

declare(strict_types=1);

namespace App\Http\Responses;

use Laravel\Fortify\Http\Responses\RegisterResponse as FortifyRegisterResponse;

class RegisterResponse extends FortifyRegisterResponse
{
    use SendsNonStaffToAtlas;
}
